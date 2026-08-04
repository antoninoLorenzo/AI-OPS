# Add a Command Policy to AI-OPS


> **Extension model:** this only works when using `ai_ops.core` directly in your own code. The API server doesn't currently expose a way to register custom policies at runtime.


Subclass `CommandAdmissionPolicy` and implement `__call__`:
 
```python
from ai_ops.core.tools.terminal.policy import CommandAdmissionPolicy, CommandContext, PolicyResult
 
class AlwaysAllowPolicy(CommandAdmissionPolicy):    

    def __call__(self, ctx: CommandContext) -> PolicyResult:
        print(f"{ctx.conversation_id}: evaluating command {ctx.command}")
        return PolicyResult(allowed=True)
```