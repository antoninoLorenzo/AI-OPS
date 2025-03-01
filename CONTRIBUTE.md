<!-- ### Table of Contents

---
-->
# Contributing

You're welcome to contribute to AI-OPS, whether you want to simply provide a feedback, help in the improvement of the
documentation or participate in the development process.

## 📌 General Rules

**Base your work on the `development` branch**—the main branch might be outdated. Ensure you update your local branch before any updates.

```bash
git checkout development
git pull origin development
```

**Branching Strategy**: create a new feature branch for your changes using a descriptive name (`fix/something`, `feature/other_thing`), for example:

```bash
git checkout -b feature/your-feature-name
```

**Logging**: do not use print statements in the API, instead use the logger provided in the `src/utils/log.py` module. For example:

```python
from src.utils.log import get_logger 
logger = get_logger(__name__)
```

### Testing New Functionality

When implementing a new feature, that's appreciated including tests (using **pytest**), this ensures that your changes work as expected; you can find existing tests under `test/`.

Thank you for your contributions and for helping improve AI-OPS!
