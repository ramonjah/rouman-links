"""Sync public Spotify artist widget order. Fail closed; never publish partial data."""
import json, re, unicodedata, subprocess
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

ARTIST = '1l3F9u1ySUlZbp3cbl4ZmZ'
ROOT = Path(__file__).resolve().parents[1]
def normalize(title):
    title = title.replace('(Annual Sampler 2026)', '').replace(' - ', ' ')
    return ''.join(c for c in unicodedata.normalize('NFKC', title).casefold() if c.isalnum())
def main():
    url = f'https://open.spotify.com/embed/artist/{ARTIST}'
    html = subprocess.check_output(['curl','--fail','--silent','--show-error','--location','--max-time','40',url], text=True)
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not match: raise ValueError('Spotify widget data missing; preserving previous snapshot')
    entity = json.loads(match[1])['props']['pageProps']['state']['data']['entity']
    if entity['id'] != ARTIST or entity['subtitle'] != 'Top tracks': raise ValueError('Wrong Spotify artist or list')
    tracks = entity['trackList']
    if len(tracks) != 10 or len({t['uri'] for t in tracks}) != 10: raise ValueError('Incomplete Spotify top ten')
    catalog = json.loads((ROOT/'release-catalog.json').read_text())
    result = []
    for rank, track in enumerate(tracks, 1):
        if 'rouman' not in track['subtitle'].casefold() or not re.fullmatch(r'spotify:track:[A-Za-z0-9]{22}',track['uri']): raise ValueError('Invalid track identity')
        matches = [i for i,item in enumerate(catalog) if normalize(item['title']) == normalize(track['title'])]
        if len(matches) > 1: raise ValueError('Ambiguous catalog match')
        cover = None
        if not matches:
            track_url = 'https://open.spotify.com/track/'+track['uri'].split(':')[-1]
            metadata = json.loads(subprocess.check_output(['curl','--fail','--silent','--show-error','--location','--max-time','40','https://open.spotify.com/oembed?'+urlencode({'url':track_url})], text=True))
            cover = metadata.get('thumbnail_url')
            host = urlparse(cover or '').hostname or ''
            if metadata.get('provider_name') != 'Spotify' or normalize(metadata.get('title','')) != normalize(track['title']) or not cover.startswith('https://') or not (host.endswith('.spotifycdn.com') or host == 'i.scdn.co'):
                raise ValueError('Unverified Spotify artwork; preserving previous snapshot')
        result.append({'catalogIndex':matches[0] if matches else None, 'artist':track['subtitle'], 'cover':cover, 'preview':(track.get('audioPreview') or {}).get('url'), 'rank':rank, 'title':track['title'], 'url':'https://open.spotify.com/track/'+track['uri'].split(':')[-1]})
    data = {'provider':'Spotify','artistId':ARTIST,'source':url,'updatedAt':datetime.now(timezone.utc).isoformat(), 'tracks':result}
    target=ROOT/'spotify-top.json'
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');temp.replace(target)
    print('Verified ten Spotify tracks; snapshot updated')
if __name__ == '__main__': main()
