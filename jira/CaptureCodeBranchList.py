from jira import JiraServer

jira = JiraServer(jiraServer, username, password)

featureBranchList = jira.captureJIRAIssueIds(jiraIssuesMap)
