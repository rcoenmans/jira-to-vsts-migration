import time

from jiraclient.jiraclient import JiraClient

from vstsclient.vstsclient import VstsClient
from vstsclient.models import JsonPatchDocument, JsonPatchOperation
from vstsclient.constants import SystemFields, MicrosoftFields, State, LinkTypes

def fetch_issue_ids(client):
    result = []

    # Query params (search should return 50 items at a time)
    n, m = 0, 50
    
    # Search for all issues that are not closed and of type User Story, Task or Bug and haven't been part of a sprint. 
    jql = 'status != Closed AND issuetype in (\"User Story\", Task, Bug) AND Sprint is EMPTY AND (\"Epic Link\" is EMPTY OR \"Epic Link\" != Maintenance) AND (fixVersion is EMPTY OR fixVersion != \"On Hold\") ORDER BY Rank ASC'

    tmp = client.search(jql, n, m)
    result += tmp

    # Issue subsequent request to get all results
    while len(tmp) == m:
        n += m
        tmp = client.search(jql, n, m)
        result += tmp

    return result

def fetch_issue(client, id):
    return client.get_issue(id)

def fetch_workitem(client, title):
    try: 
        query  = "Select [System.Id] From WorkItems Where [System.Title] = '{}'".format(title)
        result = vsts_client.query(query, 'Contoso')

        if len(result.rows) > 0:
            return client.get_workitems_by_id(result.rows[0].id)
        else:
            return None
    except:
        return None

def map_status(status):
    if status.lower() == 'in progress':
        return State.ACTIVE
    elif status.lower() == 'open':
        return State.NEW
    elif status.lower() == 'closed':
        return State.CLOSED
    else:
        return State.NEW


# Connect to JIRA
jira_client = JiraClient("<url to jira environment>")

# Connect to VSTS
vsts_client = VstsClient("dev.azure.com/<organisation>", "<personal access token>")

# Fetch all issues from Jira
issue_ids = fetch_issue_ids(jira_client)

for issue_id in issue_ids:
    # Fetch all attributes of an issue
    issue = fetch_issue(jira_client, issue_id.id)
    issue_title = "{}: {}".format(issue.key, issue.summary)

    # See if we can find this issue in VSTS
    workitem = fetch_workitem(vsts_client, issue_title)

    if workitem is None:
        doc = JsonPatchDocument() 
        doc.add(JsonPatchOperation('add', SystemFields.TITLE, issue_title))
        doc.add(JsonPatchOperation('add', SystemFields.DESCRIPTION, issue.description))
        doc.add(JsonPatchOperation('add', SystemFields.CREATED_BY, '{} <{}>'.format(issue.creator.display, issue.creator.email)))
        doc.add(JsonPatchOperation('add', SystemFields.CREATED_DATE, issue.created))
        doc.add(JsonPatchOperation('add', SystemFields.CHANGED_DATE, issue.updated))
        doc.add(JsonPatchOperation('add', SystemFields.STATE, map_status(issue.status)))
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
        workitem = vsts_client.create_workitem('Contoso', issue.type, doc, True)
    
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

    # Lets wait 2 seconds to prevent request throttling
    time.sleep(2)