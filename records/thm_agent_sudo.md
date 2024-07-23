# Agent Sudo THM

The target machine is [Agent Sudo](https://tryhackme.com/r/room/agentsudoctf), a Linux machine, the tasks went from some
basic **Enumeration** to **FTP** access, **Image Stenography**; the last task was **Linux Privilege Escalation** based 
on a <ins>sudo vulnerability</ins>.

## Reconnaissance
- ( 1 ) correctly proposed nmap and gobuster commands
- ( 0 ) proposed inspecting page, http headers, whois and (yielded no results)
- ( 1 ) given the hint from the **CTF** it successfully found the ftp username  

**Overall Usefulness**: it was quite useful for the third step, without AI-OPS I would have been blocked for a while. 

## Initial Access
- ( 0 ) Without being provided with proper tooling it suggested trying to use ftpbuster
- ( 1 ) When told to use hydra it got the command right, and with rockyou.txt it yielded successful password cracking
- ( 1 ) It assisted with image stenography successfully 

**Overall Usefulness**: This was the phase where having AI-OPS was most useful

## Privilege Escalation

- ( 0 ) Proposed wrong nmap scripts for searching for vulnerabilities, then proposed 
`sudo nmap -p- --script vuln 10.10.91.104`, that is better with `-p 21,22,80`, however it yielded CVEs to further 
explore. At the end it comes out that this was a rabbit hole.

**Overall Usefulness**: For linux privilege escalation it was not useful at all.


> Notes : 
> 
> 1. If provided with `hydra` it would have accessed FTP at the first attempt.
> 
> 2. If provided with the possibility to explore the remote machine, maybe, would have done better