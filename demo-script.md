# demo-script

## Run example eg0-basic

Used screenshot utility to capture the terminal session:

```bash

cd ~/git
git clone https://github.com/robertmuil/pythinfer.git
cd pythinfer/example_projects/eg0-basic
uvx ~/git/pythinfer query select_who_knows_whom.rq
arq --data=basic-data.ttl --data=basic-model.ttl --query=select_who_knows_whom.rq
```

## Convert to gif

Then converted to gif with:

```bash
ffmpeg -i demo-eg0-raw.mov -vf "fps=5,scale=1600:-1" -c:v gif demo-eg0.gif
```
