"""Export actual AMBuild C/C++ tasks; no guessed flags or log parsing."""
import argparse
import json
from pathlib import Path


def main():
    from ambuild2 import database, nodetypes
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);a=p.parse_args()
    root=a.build.resolve();db=database.Database(str(root/'.ambuild2/graph'));db.connect()
    rows=[]
    try: db.query_commands(rows.append)
    finally: db.close()
    entries=[]
    for node in rows:
        if node.type!=nodetypes.Cxx: continue
        args=node.blob['argv'];cwd=root/(node.folder.path if node.folder else '')
        sources=[(cwd/arg).resolve() for arg in args if arg.endswith(('.cpp','.cc','.c','.cxx')) and (cwd/arg).is_file()]
        if len(sources)!=1: raise ValueError('Ambiguous AMBuild compilation source')
        entries.append({'directory':str(cwd),'file':str(sources[0]),'arguments':args})
    if not entries: raise ValueError('AMBuild has no compilation tasks')
    (root/'compile_commands.json').write_text(json.dumps(entries,indent=2)+'\n')
    print('Exported actual compilation commands:',len(entries))


if __name__ == '__main__':
    main()
