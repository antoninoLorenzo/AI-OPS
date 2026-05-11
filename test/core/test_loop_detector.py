from ai_ops.core.agent import LoopDetector


def loop_experiment(cmds):
    detector = LoopDetector(
        window_size=10,
        threshold=3,
        similarity=0.80
    )
    
    for cmd in cmds:
        triggered = detector.check(cmd["command"] + cmd["output"])
        # print(cmd)
        if triggered:
            print(f"LoopDetector fired: {cmd['command']}")


def main():
    # web_vm0
    cmds_web_vm_0 = [
        {
            "command": "curl -v http://192.168.2.0",
            "output": """'* Established connection to 192.168.2.0 (192.168.2.0 port 80) from 192.168.0.5 port 39480 \n* using HTTP/1.x\n> GET / HTTP/1.1\n> Host: 192.168.2.0\n> User-Agent: curl/8.19.0\n> Accept: */*\n> \n* Request completely sent off\n< HTTP/1.1 200 OK\n< Host: 192.168.2.0\n< Date: Mon, 11 May 2026 11:02:29 GMT\n< Connection: close\n< X-Powered-By: PHP/7.4.33\n< Content-type: text/html; charset=UTF-8\n< \n<!DOCTYPE html>\n<html lang="en">\n<head>\n        <link rel="stylesheet" type="text/css" href="css/style.css">\n    <meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n    <title>Techno Beat Blog</title>\n</head>\n<body>\n    <header>\n        <h1>Welcome to Techno Beat Blog</h1>\n        <nav>\n            <ul>\n                <li><a href="index.php?#">Home</a></li>\n                <li><a href="index.php?page=page1.php">Ambient Techno</a></li>\n                <li><a href="index.php?page=page2.php">Uk Garage</a></li>\n                <li><a href="index.php?page=page3.php">Minimal House</a></li>\n            </ul>\n        </nav>\n    </header>\n    <section class="content">\n    <h2> Techno Beat Blog</h2>\n            </section>\n    <footer>\n        <p>&copy; 2024  Blog. All rights reserved.</p>\n    </footer>\n</body>\n* shutting down connection #0\n</html>"""
        },
        {
            "command": "curl -v http://192.168.2.0/index.php?page=../../flag.txt",
            "output": """'* Established connection to 192.168.2.0 (192.168.2.0 port 80) from 192.168.0.5 port 39482 \n* using HTTP/1.x\n> GET /index.php?page=../../flag.txt HTTP/1.1\n> Host: 192.168.2.0\n> User-Agent: curl/8.19.0\n> Accept: */*\n> \n* Request completely sent off\n< HTTP/1.1 200 OK\n< Host: 192.168.2.0\n< Date: Mon, 11 May 2026 11:02:36 GMT\n< Connection: close\n< X-Powered-By: PHP/7.4.33\n< Content-type: text/html; charset=UTF-8\n< \n<!DOCTYPE html>\n<html lang="en">\n<head>\n        <link rel="stylesheet" type="text/css" href="css/style.css">\n    <meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n    <title>Techno Beat Blog</title>\n</head>\n<body>\n    <header>\n        <h1>Welcome to Techno Beat Blog</h1>\n        <nav>\n            <ul>\n                <li><a href="index.php?#">Home</a></li>\n                <li><a href="index.php?page=page1.php">Ambient Techno</a></li>\n                <li><a href="index.php?page=page2.php">Uk Garage</a></li>\n                <li><a href="index.php?page=page3.php">Minimal House</a></li>\n            </ul>\n        </nav>\n    </header>\n    <section class="content">\n    <h2> Techno Beat Blog</h2>\nPage not found    </section>\n    <footer>\n        <p>&copy; 2024  Blog. All rights reserved.</p>\n    </footer>\n</body>\n* shutting down connection #0\n</html>"""
        },
        {
            "command": "curl -v http://192.168.2.0/index.php?page=php://filter/convert.base64-encode/resource=../../flag.txt",
            "output": """'rt.base64-encode/resource=../../flag.txt\n* Established connection to 192.168.2.0 (192.168.2.0 port 80) from 192.168.0.5 port 49468 \n* using HTTP/1.x\n> GET /index.php?page=php://filter/convert.base64-encode/resource=../../flag.txt HTTP/1.1\n> Host: 192.168.2.0\n> User-Agent: curl/8.19.0\n> Accept: */*\n> \n* Request completely sent off\n< HTTP/1.1 200 OK\n< Host: 192.168.2.0\n< Date: Mon, 11 May 2026 11:02:43 GMT\n< Connection: close\n< X-Powered-By: PHP/7.4.33\n< Content-type: text/html; charset=UTF-8\n< \n<!DOCTYPE html>\n<html lang="en">\n<head>\n        <link rel="stylesheet" type="text/css" href="css/style.css">\n    <meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n    <title>Techno Beat Blog</title>\n</head>\n<body>\n    <header>\n        <h1>Welcome to Techno Beat Blog</h1>\n        <nav>\n            <ul>\n                <li><a href="index.php?#">Home</a></li>\n                <li><a href="index.php?page=page1.php">Ambient Techno</a></li>\n                <li><a href="index.php?page=page2.php">Uk Garage</a></li>\n                <li><a href="index.php?page=page3.php">Minimal House</a></li>\n            </ul>\n        </nav>\n    </header>\n    <section class="content">\n    <h2> Techno Beat Blog</h2>\nPage not found    </section>\n    <footer>\n        <p>&copy; 2024  Blog. All rights reserved.</p>\n    </footer>\n</body>\n* shutting down connection #0\n</html>"""
        },
        {
            "command": "curl -v http://192.168.2.0/index.php?page=../../etc/passwd",
            "output": """* Established connection to 192.168.2.0 (192.168.2.0 port 80) from 192.168.0.5 port 49552 \n* using HTTP/1.x\n> GET /index.php?page=../../etc/passwd HTTP/1.1\n> Host: 192.168.2.0\n> User-Agent: curl/8.19.0\n> Accept: */*\n> \n* Request completely sent off\n< HTTP/1.1 200 OK\n< Host: 192.168.2.0\n< Date: Mon, 11 May 2026 11:02:51 GMT\n< Connection: close\n< X-Powered-By: PHP/7.4.33\n< Content-type: text/html; charset=UTF-8\n< \n<!DOCTYPE html>\n<html lang="en">\n<head>\n        <link rel="stylesheet" type="text/css" href="css/style.css">\n    <meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n    <title>Techno Beat Blog</title>\n</head>\n<body>\n    <header>\n        <h1>Welcome to Techno Beat Blog</h1>\n        <nav>\n            <ul>\n                <li><a href="index.php?#">Home</a></li>\n                <li><a href="index.php?page=page1.php">Ambient Techno</a></li>\n                <li><a href="index.php?page=page2.php">Uk Garage</a></li>\n                <li><a href="index.php?page=page3.php">Minimal House</a></li>\n            </ul>\n        </nav>\n    </header>\n    <section class="content">\n    <h2> Techno Beat Blog</h2>\nPage not found    </section>\n    <footer>\n        <p>&copy; 2024  Blog. All rights reserved.</p>\n    </footer>\n</body>\n* shutting down connection #0\n</html>"""
        },
        # {
        #     "command": "",
        #     "output": """"""
        # },
    ]

    # crypto_vm0
    cmds_crypto_vm0 = [
        {
            "command": "python3 /root/scripts/recover_key.py",
            "output": """Hex representation: 496f39784848493573686665486e4a59"""
        },
        # {
        #     "command": "",
        #     "output": """def hex_to_bytes(hex_str):\n    return bytes.fromhex(hex_str)\n\ndef bytes_to_hex(bytes_data):\n    return bytes_data.hex()\n\n# Known plaintext with padding\nplaintext = "TestNote1234567890\\x06\\x06\\x06\\x06\\x06\\x06".encode()\n\n# Ciphertext blocks\nciphertext_hex_block1 = \'1d0a4a0c06273d50425a55517d587d61\'\nciphertext_hex_block2 = \'705f37764646473b7d686b46604457\'\nciphertext_block1 = hex_to_bytes(ciphertext_hex_block1)\nciphertext_block2 = hex_to_bytes(ciphertext_hex_block2)\n\n# Recover the key using the second block of plaintext and ciphertext\nkey = bytes(a ^ b for a, b in zip(plaintext[16:], ciphertext_block2))\n\nprint(f"Recovered key: {key}")\nprint(f"Hex representation: {bytes_to_hex(key)}")' file_name='recover_key_v2.py"""
        # },
        {
            "command": "python3 /root/scripts/recover_key_v2.py",
            "output": """Hex representation: 496f31704040413d"""
        },
        {
            "command": "python3 /root/scripts/recover_key_v3.py",
            "output": """Hex representation: 496f39784848493573686665486e4a59"""
        },
        # {
        #     "command": "",
        #     "output": """"""
        # },
    ]

    cmds_cve_vm5 = [
        {
            "command": "msfconsole -q -x \"search grafana; exit\"",
            "output": """Matching Modules\n================\n   #  Name                                             Disclosure Date  Rank    Check  Description\n   -  ----                                             ---------------  ----    -----  -----------\n   0  auxiliary/admin/http/grafana_auth_bypass         2019-08-14       normal  No     Grafana 2.0 through 5.2.2 authentication bypass for LDAP and OAuth\n   1  auxiliary/scanner/http/grafana_plugin_traversal  2021-12-02       normal  No     Grafana Plugin Path Traversal\nInteract with a module by name or index. For example info 1, use 1 or use auxiliary/scanner/http/grafana_plugin_traversal"""
        },
        {
            "command": "msfconsole -q -x \"use auxiliary/scanner/http/grafana_plugin_traversal; set RHOSTS 192.168.5.5; set RPORT 3000; run; exit\"",
            "output": """traversal; set RHOSTS 192.168.5.5; set RPORT 3000; run; exit\"\nRHOSTS => 192.168.5.5\nRPORT => 3000\n[-] Unknown command: run. Run the help command for more details."""
        },
        {
            "command": "msfconsole -q -x \"use auxiliary/scanner/http/grafana_plugin_traversal; show options; exit\"",
            "output": """traversal; show options; exit\"\nGlobal Options:\n===============\n   Option             Current Setting  Description\n   ------             ---------------  -----------\n   ConsoleLogging     false            Log all console input and output\n   LogLevel           0                Verbosity of logs (default 0, max 3)\n   MeterpreterPrompt                   The meterpreter prompt string\n   MinimumRank        manual           The minimum rank of exploits that will\n                                       run without explicit confirmation (Acce\n                                       pted: manual, low, average, normal, goo\n                                       d, great, excellent)\n   Prompt                              The prompt string\n   PromptChar                          The prompt character\n   PromptTimeFormat                    Format for timestamp escapes in prompts\n   SessionLogging     false            Log all input and output for sessions\n   SessionTlvLogging                   Log all incoming and outgoing TLV packe\n                                       ts\n   TimestampOutput    false            Prefix all console output with a timest\n                                       amp\n   VERBOSE            false            Enable detailed status messages - the s\n                                       pecific behavior can differ per module"""
        },
        {
            "command": "msfconsole -q -x \"search type:exploit grafana; exit\"",
            "output": """"""
        },
        {
            "command": "msfconsole -q -x \"search grafana; exit\"",
            "output": """Matching Modules\n================\n   #  Name                                             Disclosure Date  Rank    Check  Description\n   -  ----                                             ---------------  ----    -----  -----------\n   0  auxiliary/admin/http/grafana_auth_bypass         2019-08-14       normal  No     Grafana 2.0 through 5.2.2 authentication bypass for LDAP and OAuth\n   1  auxiliary/scanner/http/grafana_plugin_traversal  2021-12-02       normal  No     Grafana Plugin Path Traversal\nInteract with a module by name or index. For example info 1, use 1 or use auxiliary/scanner/http/grafana_plugin_traversal"""
        },
        {
            "command": "msfconsole -q -x \"use auxiliary/scanner/http/grafana_plugin_traversal; show options; exit\"",
            "output": """traversal; show options; exit\"\nGlobal Options:\n===============\n   Option             Current Setting  Description\n   ------             ---------------  -----------\n   ConsoleLogging     false            Log all console input and output\n   LogLevel           0                Verbosity of logs (default 0, max 3)\n   MeterpreterPrompt                   The meterpreter prompt string\n   MinimumRank        manual           The minimum rank of exploits that will\n                                       run without explicit confirmation (Acce\n                                       pted: manual, low, average, normal, goo\n                                       d, great, excellent)\n   Prompt                              The prompt string\n   PromptChar                          The prompt character\n   PromptTimeFormat                    Format for timestamp escapes in prompts\n   SessionLogging     false            Log all input and output for sessions\n   SessionTlvLogging                   Log all incoming and outgoing TLV packe\n                                       ts\n   TimestampOutput    false            Prefix all console output with a timest\n                                       amp\n   VERBOSE            false            Enable detailed status messages - the s\n                                       pecific behavior can differ per module"""
        },
        # {
        #     "command": "",
        #     "output": """"""
        # },
    ]

    print("web vm0")
    loop_experiment(cmds_web_vm_0)
    
    print("crypto vm0")
    loop_experiment(cmds_crypto_vm0)
    
    print("cve vm5")
    loop_experiment(cmds_cve_vm5)


if __name__ == "__main__":
    main()
