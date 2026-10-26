**Updated README.md for /opt/offensive Framework**

# OffensiveCtl

OffensiveCtl is a master controller intelligence tool for the /opt/offensiv[13D[K
/opt/offensive ecosystem. It provides comprehensive awareness of the local [K
directory tree, ~/.zshrc shell configurations, /opt/offensive.env global va[2D[K
variables, and the /opt/offensive/venv virtual environment state.

## Overview

OffensiveCtl is built around an Ollama AI model that analyzes requests with[4D[K
with deep awareness of how these components interconnect. The tool allows y[1D[K
you to scan, audit, prune, or query the system for various configurations a[1D[K
and tasks.

### Key Features

*   Comprehensive awareness of the local directory tree, ~/.zshrc shell con[3D[K
configurations, /opt/offensive.env global variables, and the /opt/offensive[14D[K
/opt/offensive/venv virtual environment state
*   Recursive scanning capabilities for deeper system insights
*   AI-powered analysis with Ollama model-driven recommendations
*   Command-line interface for customizable tasks and queries

## Installation and Usage

1.  Install OffensiveCtl by running `sudo apt-get install offensivectl`
2.  Run `offensivectl.py --help` to view the available commands and options[7D[K
options

### Available Commands

| Command | Description |
| --- | --- |
| `scan`   | Build a comprehensive awareness manifest, including tree, zshr[4D[K
zshrc, global envs, and venv |
| `status` | Display the current state of the master registry |
| `recursive` | Perform a recursive scan of the system for deeper insights [K
|
| `audit`  | Run an AI-powered audit of all configurations across ~/.zshrc,[9D[K
~/.zshrc, /opt/offensive.env, the venv packages, and the codebase tree |
| `prune`  | Prune unnecessary configurations and variables |
| `query` | Perform a custom query with full registry context |

### Customizing the Tool

You can customize OffensiveCtl by passing additional arguments or flags to [K
the tool. For example:

*   To specify a custom AI prompt, use `offensivectl.py --prompt="custom pr[2D[K
prompt"`
*   To select a specific Ollama model, use `offensivectl.py --model=model_n[15D[K
--model=model_name`
*   To output results to a file, use `offensivectl.py --output=output_file.[21D[K
--output=output_file.json`

## Troubleshooting

For troubleshooting issues or errors with OffensiveCtl, refer to the [offen[6D[K
[offensivectl README.md](./offensivectl/README.md) for guidance.

### Known Issues and Limitations

OffensiveCtl is still under development and may contain known issues. Pleas[5D[K
Please report any bugs or limitations at the [offensivectl issue tracker](h[10D[K
tracker](https://github.com/offensiveframework/OffensiveCtl/issues).

By following these guidelines and using OffensiveCtl effectively, you can e[1D[K
ensure the security, performance, and stability of your /opt/offensive ecos[4D[K
ecosystem.

