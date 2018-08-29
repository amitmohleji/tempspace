from jira import JiraServer

jira = JiraServer(jiraServer, username, password)

issues = jira.captureJIRAIssueIds(query)
