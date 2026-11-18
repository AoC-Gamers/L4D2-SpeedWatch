"""One channel/version identity for Make, CI packaging and explicit publication."""
import re

def resolve(ref, sha=''):
    if ref in {'main','develop'}:
        channel='latest' if ref=='main' else 'develop'
        tag='channel/'+channel;title='Latest' if ref=='main' else 'Develop'
        prerelease=ref=='develop';latest=ref=='main'
    elif re.fullmatch(r'v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?',ref):
        channel=ref[1:];tag=ref;title=ref;prerelease='-' in channel;latest=not prerelease
    else:
        if ref not in {'','local'} and not re.fullmatch(r'[0-9a-f]{40}',sha):raise ValueError('A diagnostic ref requires a full commit SHA')
        channel='local' if ref in {'','local'} else 'pr-'+sha[:7]
        if channel=='pr-' or not re.fullmatch(r'(local|pr-[0-9a-f]{7})',channel):raise ValueError('A diagnostic ref requires a full commit SHA')
        tag='';title='';prerelease=False;latest=False
    return {'linux_basename':f'l4d2-speedwatch-{channel}-linux','windows_basename':f'l4d2-speedwatch-{channel}-windows','release_tag':tag,'release_name':title,'prerelease':str(prerelease).lower(),'latest':str(latest).lower()}
