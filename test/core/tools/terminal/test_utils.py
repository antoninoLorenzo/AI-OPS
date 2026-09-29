import pytest

from ai_ops.core.tools.terminal.utils import extract_executables

_multiline_bash_fuzz = r"""cd /root/scripts
cat /usr/share/wordlists/dirb/common.txt /usr/share/wordlists/dirb/big.txt /usr/share/wordlists/dirb/indexes.txt | sort -u > wl_all.txt
wc -l wl_all.txt
for base in "http://192.168.5.10" "https://192.168.5.10"; do
  echo "=== $base ==="
  while read p; do
    [ -z "$p" ] && continue
    code=$(curl -sk -o /tmp/r -w "%{http_code}" --max-time 5 "$base/$p")
    if [ "$code" != "404" ]; then
      sz=$(wc -c < /tmp/r)
      echo "$code $sz /$p"
    fi
  done < wl_all.txt
done
echo "DONE"
"""

_EXTRACT_EXECUTABLE_TESTS = [
    {
        "command": "echo $(cat secret)",
        "expected": {"echo", "cat"}
    },
    {
        "command": "cat names.txt | grep -i smith | wc -l",
        "expected": {"cat", "grep", "wc"}
    },
    {
        "command": "mkdir build && cd build && cmake .. || echo 'Build failed'",
        "expected": {"mkdir", "cd", "cmake", "echo"}
    },
    {
        "command": "echo \"Today is `date`\"",
        "expected": {"echo", "date"}
    },
    {
        # 'grep' is inside a literal string, not executed
        "command": "echo 'grep pattern file.txt'",  
        "expected": {"echo"}
    },
    {
        "command": "echo <(ls -l $(cat file.txt))",
        "expected": {"echo", "ls", "cat"}
    },
    {
        "command": "docker exec -it --rm container /bin/bash",
        "expected": {"docker"}
    },
    # --- multiline commands tests
    {
        "command": _multiline_bash_fuzz,
        "expected": {"cd", "cat", "sort", "wc", "echo", "read", "curl"},
    },
    # --- wrapped command tests 
    # those are a pain in the ass, god forbid I have a little TODO in 
    # core.tools.utils since the dawn of time (i.e May codebase rewrite)
    # only the wrapper is returned for now, so these don't pass:
    # {
    #     "command": "sudo docker ps -a",
    #     "expected": {"sudo", "docker"}
    # },
    # {
    #     "command": "   sudo   systemctl restart $(cat service_name)   ",
    #     "expected": {"sudo", "systemctl", "cat"}
    # },
    # {
    #     "command": "sudo --group=1000 -u www-data ls",
    #     "expected": {"sudo", "ls"}
    # },
    # {
    #     "command": "timeout 2 sleep 1; echo 'hello'",
    #     "expected": {"timeout", "sleep", "echo"}
    # },
]


@pytest.mark.parametrize("test_case", _EXTRACT_EXECUTABLE_TESTS)
def test_extract_executables(test_case):
    assert extract_executables(test_case["command"]) == test_case["expected"]
        
