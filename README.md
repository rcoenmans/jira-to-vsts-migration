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

> Note that this query only returns the issue `id`.

```python
# Variable to store the result
results = []

# Query params (search should return 50 items at a time)
n, m = 0, 50
    
# Query all issues (User Story, Task or Bug) that are open and haven't been part of a sprint 
jql = 'status != Closed AND issuetype in (\"User Story\", Task, Bug) AND Sprint is EMPTY AND (\"Epic Link\" is EMPTY OR \"Epic Link\" != Maintenance) AND (fixVersion is EMPTY OR fixVersion != \"On Hold\") ORDER BY Rank ASC'

# Issue the initial query
tmp = client.search(jql, n, m)
results += tmp

# Issue subsequent queries to get all results
while len(tmp) == m:
    n += m
    tmp = client.search(jql, n, m)
    results += tmp
```
### 3. Create a work item in Azure DevOps
The next step is to create a corresponding work item in Azure DevOps for each issue in the results.
```python
for result in results:
    # We first need to get all the properties of the issue in Jira (remember the query only returns a list of ids)
    issue =  jira_client.get_issue(result.id)

    # Create a new JsonPatchDocument to capture the data of the work item
    doc = JsonPatchDocument() 
    doc.add(JsonPatchOperation('add', SystemFields.TITLE, '{}: {}'.format(issue.key, issue.summary)))
    doc.add(JsonPatchOperation('add', SystemFields.DESCRIPTION, issue.description))
    doc.add(JsonPatchOperation('add', SystemFields.CREATED_BY, '{} <{}>'.format(issue.creator.display, issue.creator.email)))
    doc.add(JsonPatchOperation('add', SystemFields.CREATED_DATE, issue.created))
    doc.add(JsonPatchOperation('add', SystemFields.CHANGED_DATE, issue.updated))
    doc.add(JsonPatchOperation('add', SystemFields.STATE, State.NEW))
    doc.add(JsonPatchOperation('add', SystemFields.REASON, 'New'))
    doc.add(JsonPatchOperation('add', MicrosoftFields.PRIORITY, issue.priority[:1]))        
    doc.add(JsonPatchOperation('add', MicrosoftFields.VALUE_AREA, 'Business'))
    
    # Migrate any comments
    if len(issue.comments) > 0:
        for comment in issue.comments:
            doc.add(JsonPatchOperation('add', SystemFields.HISTORY, comment.body))

    # Migrate assignee
    if issue.assignee is not None:
        doc.add(JsonPatchOperation('add', SystemFields.ASSIGNED_TO, '{} <{}>'.format(issue.assignee.display, issue.assignee.email)))
    
    # Migrate any labels/tags
    if len(issue.labels) > 0:
        doc.add(JsonPatchOperation('add', SystemFields.TAGS, '; '.join(issue.labels)))
    
    # Make a note that the work item has been migrated
    doc.add(JsonPatchOperation('add', SystemFields.TAGS, 'migrated'))
    doc.add(JsonPatchOperation('add', SystemFields.HISTORY, 'Migrated from Jira to Azure DevOps'))

    # Create the work item in Azure DevOps
    workitem = vsts_client.create_workitem('Contoso', issue.type, doc, bypass_rules=True)
```
> We would like to keep the original CREATED_DATE value from Jira instead of the *migration date* which Azure DevOps will populate for us automatically. Therefore, we need to set `bypass_rules=True` in the call to `vsts_client.create_workitem()`. This allows us to bypass the rules for fields that are typically automatically populated (based on current date/time, user running the script, etc.) and set them with the original values from Jira.
### 4. Migrate attachments
```python
# Migrate attachments
if len(issue.attachments) > 0:
    for attachment in issue.attachments:
        vsts_attachment = None

        # Download the attachment(s) from Jira
        with open('./tmp/{}'.format(attachment.filename), 'wb') as f:
            f.write(jira_client.download_attachment(attachment.id, attachment.filename))
        
        # Upload the attachment(s) to VSTS
        with open('./tmp/{}'.format(attachment.filename), 'rb') as f:
            vsts_attachment = vsts_client.upload_attachment(attachment.filename, f)

        # Link the attachment(s) to the work item
        vsts_client.add_attachment(workitem.id, vsts_attachment.url, 'Migrating attachment {}'.format(attachment.filename))
```
### 5. Link to Feature or Epic (OPTIONAL)
I can't remember exactly why we mapped an epic in Jira to a feature in Azure DevOps. I think Jira, back then, didn't have the concept of a *feature*. 
```python
# Link to a feature (epic in Jira is mapped to Feature in DevOps but you can link it to an Epic as well)
if issue.epic is not None:
    # Determine if the feature exists already
    feature = fetch_workitem(vsts_client, issue.epic.name)

    if feature is None:
        doc = JsonPatchDocument()
        doc.add(JsonPatchOperation('add', SystemFields.TITLE, issue.epic.name))
        doc.add(JsonPatchOperation('add', SystemFields.DESCRIPTION, issue.epic.summary))
        
        if issue.epic.done:
            doc.add(JsonPatchOperation('add', SystemFields.STATE, State.RESOLVED))
        else:
            doc.add(JsonPatchOperation('add', SystemFields.STATE, State.ACTIVE))

        # Create the feature in Azure DevOps
        feature = vsts_client.create_workitem('Contoso', 'Feature', doc)
    
    # Link the user story with feature (PARENT)
    vsts_client.add_link(workitem.id, feature.id, LinkTypes.PARENT)
```