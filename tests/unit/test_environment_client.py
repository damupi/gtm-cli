"""Tests for GTMClient environment methods (list/get/create/delete)."""

from unittest.mock import MagicMock, patch

from gtm_cli.core.client import GTMClient


class TestClientCreateEnvironment:
    def test_create_environment_includes_account_and_container_id_in_body(self):
        """The GTM API rejects environments.create unless accountId/containerId
        are present in the request BODY, not just the `parent` path — confirmed
        against the live API (400 'Invalid account_id (base 10 number expected)'
        when they're missing). create_environment must inject them.
        """
        client = GTMClient.__new__(GTMClient)
        mock_service = MagicMock()
        mock_service.accounts().containers().environments().create().execute.return_value = {
            "environmentId": "1083",
            "name": "dry-run-test",
        }

        with patch.object(client, "_get_service", return_value=mock_service):
            result = client.create_environment(
                account_id="3116374124",
                container_id="40196123",
                environment_body={
                    "name": "dry-run-test",
                    "type": "user",
                    "enableDebug": False,
                    "containerVersionId": "1",
                },
            )

        assert result["environmentId"] == "1083"

        call_kwargs = mock_service.accounts().containers().environments().create.call_args.kwargs
        assert call_kwargs["parent"] == "accounts/3116374124/containers/40196123"
        body = call_kwargs["body"]
        assert body["accountId"] == "3116374124"
        assert body["containerId"] == "40196123"
        # Caller-supplied fields must still be present, untouched
        assert body["name"] == "dry-run-test"
        assert body["type"] == "user"
        assert body["containerVersionId"] == "1"

    def test_create_environment_does_not_mutate_caller_dict(self):
        """The caller's environment_body dict must not be mutated in place."""
        client = GTMClient.__new__(GTMClient)
        mock_service = MagicMock()
        mock_service.accounts().containers().environments().create().execute.return_value = {}

        original_body = {"name": "x", "type": "user"}

        with patch.object(client, "_get_service", return_value=mock_service):
            client.create_environment(
                account_id="a1",
                container_id="c1",
                environment_body=original_body,
            )

        assert original_body == {"name": "x", "type": "user"}
