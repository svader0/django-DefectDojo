"""
The JIRA edit page must not pair the stored credential with a new destination.

``dojo.change_jira_instance`` lets a non-superuser edit the JIRA instances, but the
stored password is never shown back to that editor. Leaving the field blank used to
reuse it against whatever URL arrived in the same request, so the editor could send
a secret they cannot read to a host of their own choosing.
"""

from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from dojo.models import JIRA_Instance, User

from .dojo_test_case import DojoTestCase

PASSWORD = "stored-password-value"
NEW_PASSWORD = "replacement-password-value"
URL = "https://jira.example.com"
ATTACKER_URL = "https://attacker.example.net"


class JiraCredentialRebindTest(DojoTestCase):
    def setUp(self):
        self.jira = JIRA_Instance.objects.create(
            configuration_name="victim instance",
            url=URL,
            username="service-account",
            password=PASSWORD,
            default_issue_type="Bug",
            epic_name_id=10011,
            open_status_key=3,
            close_status_key=2,
            info_mapping_severity="Info",
            low_mapping_severity="Low",
            medium_mapping_severity="Medium",
            high_mapping_severity="High",
            critical_mapping_severity="Critical",
        )
        self.editor = User.objects.create(username="jira_instance_editor")
        self.editor.user_permissions.add(
            Permission.objects.get(content_type__app_label="dojo", codename="change_jira_instance"),
        )
        self.url = reverse("edit_jira", args=[self.jira.id])
        self.client = Client()
        self.client.force_login(self.editor)

    def _post(self, overrides):
        data = {
            "configuration_name": self.jira.configuration_name,
            "url": URL,
            "username": "service-account",
            "password": "",
            "default_issue_type": "Bug",
            "epic_name_id": "10011",
            "open_status_key": "3",
            "close_status_key": "2",
            "info_mapping_severity": "Info",
            "low_mapping_severity": "Low",
            "medium_mapping_severity": "Medium",
            "high_mapping_severity": "High",
            "critical_mapping_severity": "Critical",
            "issue_template_dir": "",
        }
        data.update(overrides)
        # Every outbound call funnels through the helper, from the form and the view alike.
        with patch("dojo.jira.helper.get_jira_connection_raw") as connect:
            response = self.client.post(self.url, data)
        self.jira.refresh_from_db()
        return response, connect.call_args_list

    def test_a_new_url_does_not_get_the_stored_credential(self):
        response, calls = self._post({"url": ATTACKER_URL})
        self.assertEqual(calls, [], "the stored credential left for the submitted URL")
        self.assertEqual(self.jira.url, URL)
        self.assertEqual(self.jira.password, PASSWORD)
        self.assertContains(response, "Enter the password or token again")

    def test_a_new_url_is_accepted_when_the_credential_is_supplied(self):
        response, calls = self._post({"url": ATTACKER_URL, "password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(calls[0].args, (ATTACKER_URL, "service-account", NEW_PASSWORD))
        self.assertEqual(self.jira.url, ATTACKER_URL)
        self.assertEqual(self.jira.password, NEW_PASSWORD)

    def test_a_blank_credential_is_still_reused_for_the_same_url(self):
        response, calls = self._post({"configuration_name": "renamed instance"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(calls[0].args, (URL, "service-account", PASSWORD))
        self.assertEqual(self.jira.configuration_name, "renamed instance")
        self.assertEqual(self.jira.password, PASSWORD)

    def test_a_trailing_slash_alone_is_not_a_new_url(self):
        response, _calls = self._post({"url": URL + "/"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.jira.password, PASSWORD)
