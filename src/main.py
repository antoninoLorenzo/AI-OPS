

def run_api():
    pass


if __name__ == "__main__":
    from src.agent.tools import TOOLS, Terminal

    for tool in TOOLS:
        print(tool.get_documentation())

    out = Terminal.run('ls')
    print(out)
