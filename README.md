# Jira to Azure DevOps migration
A Jira to Azure DevOps migration script written in Python. This script was created and used during a project where issues (user stories, bugs and tasks) were maintained in Jira and the code in Azure DevOps. Back then, there wasn't any integration between Jira and Azure DevOps (or VSTS as it was called). 

We decided to move everything to Azure DevOps so we have full traceability on all the work that's been done. And since nobody wanted to migrate 50+ user stories by hand, I decided to write a simple migration script that copies the most important bits of information.

## Getting started
The script relies on 2 python libraries that you'll find on PyPi.
```bash
$ pip install vsts-client
$ pip install jira-client
```

## Migration script
### 1. Connect to Jira and Azure DevOps
To connect to Jira simply provide your user name/password to the client. In order to connect to Azure DevOps, you need to obtain a [personal access token](https://docs.microsoft.com/en-us/vsts/integrate/get-started/authentication/pat).
```python
# Connect to JIRA
jira_client = JiraClient("<organisation>.atlassian.net", "<username>", "<password>")

# Connect to VSTS
vsts_client = VstsClient("dev.azure.com/<organisation>", "<personal access token>")
```

### 2. Query all issues that need to be migrated
