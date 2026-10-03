import abc
from enum import StrEnum
from dataclasses import dataclass
from typing import List, Dict, Literal, ClassVar

from pydantic import BaseModel, Field

CVE_TASKS = [
    "cve-2024-36401",  # vm0  - GeoServer 2.23.2 (OGC filter evaluation RCE)
    "cve-2024-23897",  # vm1  - Jenkins 2.441 (CLI arbitrary file read)
    "cve-2022-22965",  # vm2  - Spring Framework / Tomcat (Spring4Shell RCE)
    "cve-2021-3156",   # vm3  - sudo 1.8.31 (Baron Samedit heap overflow LPE)
    "cve-2021-42013",  # vm4  - Apache httpd 2.4.50 (path traversal RCE)
    "cve-2021-43798",  # vm5  - Grafana 8.2.0 (directory traversal)
    "cve-2021-25646",  # vm6  - Apache Druid 0.20.0 (embedded JS RCE)
    "cve-2021-44228",  # vm7  - Apache Solr 8.11.0 (Log4Shell RCE)
    "cve-2019-16113",  # vm8  - Bludit 3.9.2 (directory traversal RCE)
    "cve-2017-7494",   # vm9  - Samba 4.6.3 (SambaCry RCE)
    "cve-2014-0160",   # vm10 - OpenSSL 1.0.1c / nginx (Heartbleed)
]
IN_VITRO_CATEGORIES = ["access_control", "cryptography", "network_security", "web_security"]

class InVitroCategories(StrEnum):
    AccessControl = "access_control"
    WebSecurity = "web_security"
    NetworkSecurity = "network_security"
    Cryptography = "cryptography"


class InVitroTaskSet(BaseModel):
    enabled: bool = True
    tasks: Dict[InVitroCategories, List[str]] = {
        InVitroCategories.AccessControl: [
            "in-vitro_access_control_vm0",
            "in-vitro_access_control_vm1",
            "in-vitro_access_control_vm2",
            "in-vitro_access_control_vm3",
            "in-vitro_access_control_vm4"
        ],
        InVitroCategories.WebSecurity: [
            "in-vitro_web_security_vm0",
            "in-vitro_web_security_vm1",
            "in-vitro_web_security_vm2",
            "in-vitro_web_security_vm3",
            "in-vitro_web_security_vm4",
            "in-vitro_web_security_vm5",
            "in-vitro_web_security_vm6"
        ],
        InVitroCategories.NetworkSecurity: [
            "in-vitro_network_security_vm0",
            "in-vitro_network_security_vm1",
            "in-vitro_network_security_vm2",
            "in-vitro_network_security_vm3",
            "in-vitro_network_security_vm4",
            "in-vitro_network_security_vm5"
        ],
        InVitroCategories.Cryptography: [
            "in-vitro_cryptography_vm0",
            "in-vitro_cryptography_vm1",
            "in-vitro_cryptography_vm2",
            "in-vitro_cryptography_vm3"
        ]
    }


class RealWorldTaskSet(BaseModel):
    enabled: bool = True
    tasks: List[str] = CVE_TASKS


class AutoPenBenchRun(BaseModel):
    model: str
    in_vitro: InVitroTaskSet
    real_world: RealWorldTaskSet
    dry_run: bool = False
    excluded_tools: List[str] = Field(default_factory=list)
    

class Task(abc.ABC, BaseModel):
    difficulty: ClassVar[Literal["in-vitro", "real-world"]]
    task: str
    flag: str
    target: str
    vulnerability: str
    command_milestones: List[str]
    stage_milestones: List[str]


class InVitroTask(Task, BaseModel):
    difficulty: ClassVar[Literal["in-vitro", "real-world"]] = "in-vitro"
    category: Literal["access_control", "web_security", "network_security", "cryptography"]


class RealWorldTask(Task, BaseModel):
    difficulty: ClassVar[Literal["in-vitro", "real-world"]] = "real-world"
    alias: str


@dataclass
class ToolCallRuntime:
    start: float
    end: float = -1.0
    