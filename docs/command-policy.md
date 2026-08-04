# Command Policies in AI-OPS

The `Terminal` tool gives the AI-OPS agent the capability to execute arbitrary bash commands. To *prevent the execution of dangerous commands* you can configure **Command Admission Policies** that are always verified before any command is actually executed within the agent container. When the agent executes in *unsupervised* mode and a policy block execution the command is never executed, in *supervised* mode the command will require the user to approve it (with a timeout that corresponds to a deny).


You can configure command policies in `"~/.local/share/ai_ops/agent_config.json"` as follows:
```json
{
    "command_policies": [
        {
            "kind": "allowlist",
            "params": {
                "allowlist": ["nmap", "ffuf"]
            }
        } 
    ]
}
```

The `AllowListPolicy` has a list of safe defaults that is extended with the binary names in `allowlist`.

To implement a new policy see [How To Add a Command Policy](how-to/add-a-command-policy.md).