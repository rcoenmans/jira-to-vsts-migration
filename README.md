# Jira to Azure DevOps migration
A Jira to Azure DevOps migration script written in Python. This script was created and used during a project where issues (user stories, bugs and tasks) were maintained in Jira and the code was stored in Azure DevOps. Back then there wasn't any integration between Jira and Azure DevOps (or VSTS as it was called) so we had to go back and forth. 

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
For our particular project, we're migrating all user stories, tasks and bugs that are still open and not part of any sprint (previous or current). Note that the query returns 50 results at a time and keeps on querying untill it has fetched all items. 
```python
# Variable to store the result
result = []

# Query params (search should return 50 items at a time)
n, m = 0, 50
    
# Query all issues (User Story, Task or Bug) that are open and haven't been part of a sprint 
jql = 'status != Closed AND issuetype in (\"User Story\", Task, Bug) AND Sprint is EMPTY AND (\"Epic Link\" is EMPTY OR \"Epic Link\" != Maintenance) AND (fixVersion is EMPTY OR fixVersion != \"On Hold\") ORDER BY Rank ASC'

# Issue the initial query
tmp = client.search(jql, n, m)
result += tmp

# Issue subsequent queries to get all results
while len(tmp) == m:
    n += m
    tmp = client.search(jql, n, m)
    result += tmp
```