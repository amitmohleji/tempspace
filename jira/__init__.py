import string
import com.xhaus.jyson.JysonCodec as Json
from util import error
from xlrelease.HttpRequest import HttpRequest
import datetime


class JiraServer:

    def __init__(self, jira_server, username, password, encoding='utf-8'):
        if jira_server is None:
            error('No server provided.')

        self.jira_server = jira_server
        self.username = username
        self.password = password
        self.encoding = encoding

    def queryIssues(self, query, options=None):

        if not query:
            error('No JQL query provided.')

        # Create POST body
        content = {
            'jql': query,
            'startAt': 0,
            'fields': ['summary', 'status', 'assignee'],
            'maxResults': 1000
        }
        # Do request
        request = self._createRequest()
        response = request.post('/rest/api/2/search', self._serialize(content), contentType='application/json')
        # Parse result
        if response.status == 200:
            issues = {}
            data = Json.loads(response.response)
            for item in data['issues']:
                issue = item['key']
                assignee = "Unassigned" if (item['fields']['assignee'] is None) else item['fields']['assignee']['displayName']
                issues[issue] = {
                    'issue'   : issue,
                    'summary' : item['fields']['summary'],
                    'status'  : item['fields']['status']['name'],
                    'assignee': assignee,
                    'link'    : "{1}/browse/{0}".format(issue, self.jira_server['url'])
                }
            return issues
        else:
            error(u"Failed to execute search '{0}' in JIRA.".format(query), response)

    def query(self, query):
        if not query:
            error('No JQL query provided.')

        # Create POST body
        content = {
            'jql': query,
            'startAt': 0,
            'fields': ['summary'],
            'maxResults': 1000
        }

        # Do request
        request = self._createRequest()
        response = request.post('/rest/api/2/search', self._serialize(content), contentType='application/json')
        # Parse result
        if response.status == 200:
            data = Json.loads(response.response)

            print "#### Issues found"
            issues = {}
            for item in data['issues']:
                issue = item['key']
                issues[issue] = item['fields']['summary']
                print u"* {0} - {1}".format(self._link(issue), item['fields']['summary'])
            print "\n"
            return issues

        else:
            error(u"Failed to execute search '{0}' in JIRA.".format(query), response)

    def createIssue(self, project, title, description, issue_type):
        # Create POST body
        content = {
            'fields': {
                'project': {
                    'key': project
                },
                'summary': title,
                'description': description,
                'issuetype': {
                    'name': string.capwords(issue_type)
                }
            }
        }

        # Do request
        request = self._createRequest()
        response = request.post('/rest/api/2/issue', self._serialize(content), contentType='application/json')

        # Parse result
        if response.status == 201:
            data = Json.loads(response.response)
            issue_id = data.get('key')
            print u"Created {0} in JIRA.".format(self._link(issue_id))

            return issue_id
        else:
            error("Failed to create issue in JIRA.", response)

    def updateIssue(self, issue_id, new_status, comment, labels, new_summary=None):
        # Check for ticket
        self._checkIssue(issue_id)

        updated_data = self._getUpdatedIssueData(new_summary, comment, labels)

        # Status transition
        if new_status:
            self._transitionIssue(issue_id, new_status)
            self._updateIssue(issue_id, updated_data)
        else:
            self._updateIssue(issue_id, updated_data)

        print u"Updated {0}".format(self._link(issue_id))
        print

    ######

    def _getUpdatedIssueData(self, summary, comment, labels):
        updated_data = {}

        if comment:
            updated_data.update({
                "comment": [
                    {
                        "add": {
                            "body": comment
                        }
                    }
                ]
            })

        if summary:
            updated_data.update({
                "summary": [
                    {
                        "set": summary
                    }
                ]
            })
        if labels:
            updated_data.update(
                {
                    "labels" : [{"add" :item} for item in labels]
                })

        return updated_data

    def _updateIssue(self, issue_id, updated_data):

        # Create POST body
        request_data = {"update": updated_data}

        # Do request
        request = self._createRequest()
        response = request.put(self._issueUrl(issue_id), self._serialize(request_data), contentType='application/json')

        # Parse result
        if response.status != 204:
            error(u"Unable to update issue {0}. Please make sure the issue is not in a 'closed' state.".format(self._link(issue_id)), response)

    def _transitionIssue(self, issue_id, new_status):

        issue_url = self._issueUrl(issue_id)

        # Find possible transitions
        request = self._createRequest()
        response = request.get(issue_url + "/transitions?expand=transitions.fields", contentType='application/json')

        if response.status != 200:
            error(u"Unable to find transitions for issue {0}".format(self._link(issue_id)), response)

        transitions = Json.loads(response.response)['transitions']

        # Check  transition
        wanted_transaction = -1
        for transition in transitions:
            if transition['to']['name'].lower() == new_status.lower():
                wanted_transaction = transition['id']
                break

        if wanted_transaction == -1:
            error(u"Unable to find status {0} for issue {1}".format(new_status, self._link(issue_id)))

        # Prepare POST body
        transition_data = {
            "transition": {
                "id": wanted_transaction
            }
        }

        # Perform transition
        response = request.post(issue_url + "/transitions?expand=transitions.fields", self._serialize(transition_data), contentType='application/json')

        if response.status != 204:
            error(u"Unable to perform transition {0} for issue {1}".format(wanted_transaction, self._link(issue_id)), response)

    def _createRequest(self):
        return HttpRequest(self.jira_server, self.username, self.password)

    def _link(self, issue_id):
        return "[{0}]({1}/browse/{0})".format(issue_id, self.jira_server['url'])

    def _issueUrl(self, issue_id):
        return "/rest/api/2/issue/" + issue_id

    def _checkIssue(self, issue_id):
        request = self._createRequest()
        response = request.get(self._issueUrl(issue_id), contentType='application/json')

        if response.status != 200:
            error(u"Unable to find issue {0}".format(self._link(issue_id)), response)

    def _serialize(self, content):
        return Json.dumps(content).encode(self.encoding)

    def createVersion(self, versionName, description, project):
        data = {
                    "description": description,
                    "name": versionName,
                    "project": project,
                    "startDate" : str(datetime.date.today())
                }
        createVersionUrl = "/rest/api/2/version"
        request = self._createRequest()
        response = request.post(createVersionUrl, self._serialize(data), contentType='application/json')
        if response.status != 201:
            error(u"Unable to create version {0} for project {1}".format(versionName,project), response)
        return Json.loads(response.response)['id']

    def releaseVersion(self, versionId):
        data = {
                    "released": "true",
                    "releaseDate" : str(datetime.date.today())
                }
        createVersionUrl = "/rest/api/2/version/%s" %   versionId 
        request = self._createRequest()
        response = request.put(createVersionUrl, self._serialize(data), contentType='application/json')
        if response.status != 200:
            error(u"Unable to release versionId {0}".format(versionId), response)
    
    def captureJIRAIssueIds(self,query):
        if not query:
            error('No JQL query provided.')

        # Create POST body
        content = {
            'jql': query,
            'startAt': 0,
            'fields': ['summary'],
            'maxResults': 1000
        }

        # Do request
        request = self._createRequest()
        response = request.post('/rest/api/2/search', self._serialize(content), contentType='application/json')
        # Parse result
        if response.status == 200:
            data = Json.loads(response.response)

            print "#### Issues found"
            issues = {}
            for item in data['issues']:
                issue = item['key']
                issues[issue] = item['id']
                print u"* {0} - {1}".format(self._link(issue), item['fields']['summary'])
            print "\n"
            return issues

        else:
            error(u"Failed to execute search '{0}' in JIRA.".format(query), response)

    def captureCodeBranchList(self,issueList):
        featureList = []
        codeBranchUrl = "/rest/dev-status/1.0/issue/detail?issueId=%s&applicationType=stash&dataType=pullrequest"
        request = self._createRequest()
        for item in issueList.values():
            response = request.get(codeBranchUrl % item, contentType='application/json')
            if response.status == 200:
                data = Json.loads(response.response)
                for branch in data['detail'][0]['branches']:
                    featureList.append(branch['name'])
        return featureList

