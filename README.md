# agent-skills-manager

Global agent skill manager for OpenCode and Junie. Python 3, standard library only.

## Install

```bash
./install.sh
```

Ensures `~/.local/bin` is on PATH.

## Usage

```bash
agent-skills init
agent-skills list
agent-skills detect
agent-skills recommend
agent-skills add flutter-tamim
agent-skills validate
agent-skills sync
agent-skills junie
agent-skills opencode plan
agent-skills opencode apply
```

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
