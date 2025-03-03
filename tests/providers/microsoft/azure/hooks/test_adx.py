#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import json
import os
from unittest import mock
from unittest.mock import patch

import pytest
from azure.kusto.data import ClientRequestProperties, KustoClient, KustoConnectionStringBuilder
from pytest import param

from airflow.exceptions import AirflowException
from airflow.models import Connection
from airflow.providers.microsoft.azure.hooks.adx import AzureDataExplorerHook
from airflow.utils import db
from airflow.utils.session import create_session
from tests.test_utils.providers import get_provider_min_airflow_version

ADX_TEST_CONN_ID = "adx_test_connection_id"


class TestAzureDataExplorerHook:
    def teardown_method(self):
        with create_session() as session:
            session.query(Connection).filter(Connection.conn_id == ADX_TEST_CONN_ID).delete()

    def test_conn_missing_method(self):
        db.merge_conn(
            Connection(
                conn_id=ADX_TEST_CONN_ID,
                conn_type="azure_data_explorer",
                login="client_id",
                password="client secret",
                host="https://help.kusto.windows.net",
                extra=json.dumps({}),
            )
        )
        with pytest.raises(AirflowException) as ctx:
            AzureDataExplorerHook(azure_data_explorer_conn_id=ADX_TEST_CONN_ID)
            assert "is missing: `data_explorer__auth_method`" in str(ctx.value)

    def test_conn_unknown_method(self):
        db.merge_conn(
            Connection(
                conn_id=ADX_TEST_CONN_ID,
                conn_type="azure_data_explorer",
                login="client_id",
                password="client secret",
                host="https://help.kusto.windows.net",
                extra=json.dumps({"auth_method": "AAD_OTHER"}),
            )
        )
        with pytest.raises(AirflowException) as ctx:
            AzureDataExplorerHook(azure_data_explorer_conn_id=ADX_TEST_CONN_ID)
        assert "Unknown authentication method: AAD_OTHER" in str(ctx.value)

    def test_conn_missing_cluster(self):
        db.merge_conn(
            Connection(
                conn_id=ADX_TEST_CONN_ID,
                conn_type="azure_data_explorer",
                login="client_id",
                password="client secret",
                extra=json.dumps({}),
            )
        )
        with pytest.raises(AirflowException) as ctx:
            AzureDataExplorerHook(azure_data_explorer_conn_id=ADX_TEST_CONN_ID)
        assert "Host connection option is required" in str(ctx.value)

    @mock.patch.object(KustoClient, "__init__")
    def test_conn_method_aad_creds(self, mock_init):
        mock_init.return_value = None
        db.merge_conn(
            Connection(
                conn_id=ADX_TEST_CONN_ID,
                conn_type="azure_data_explorer",
                login="client_id",
                password="client secret",
                host="https://help.kusto.windows.net",
                extra=json.dumps(
                    {
                        "tenant": "tenant",
                        "auth_method": "AAD_CREDS",
                    }
                ),
            )
        )
        AzureDataExplorerHook(azure_data_explorer_conn_id=ADX_TEST_CONN_ID)
        assert mock_init.called_with(
            KustoConnectionStringBuilder.with_aad_user_password_authentication(
                "https://help.kusto.windows.net", "client_id", "client secret", "tenant"
            )
        )

    @mock.patch("azure.identity._credentials.environment.ClientSecretCredential")
    def test_conn_method_token_creds(self, mock1):
        db.merge_conn(
            Connection(
                conn_id=ADX_TEST_CONN_ID,
                conn_type="azure_data_explorer",
                host="https://help.kusto.windows.net",
                extra=json.dumps(
                    {
                        "auth_method": "AZURE_TOKEN_CRED",
                    }
                ),
            )
        )
        with patch.dict(
            in_dict=os.environ,
            values={
                "AZURE_TENANT_ID": "tenant",
                "AZURE_CLIENT_ID": "client",
                "AZURE_CLIENT_SECRET": "secret",
            },
        ):
            hook = AzureDataExplorerHook(azure_data_explorer_conn_id=ADX_TEST_CONN_ID)
            assert hook.connection._kcsb.data_source == "https://help.kusto.windows.net"
            mock1.assert_called_once_with(
                tenant_id="tenant",
                client_id="client",
                client_secret="secret",
                authority="https://login.microsoftonline.com",
            )

    @mock.patch.object(KustoClient, "__init__")
    def test_conn_method_aad_app(self, mock_init):
        mock_init.return_value = None
        db.merge_conn(
            Connection(
                conn_id=ADX_TEST_CONN_ID,
                conn_type="azure_data_explorer",
                login="app_id",
                password="app key",
                host="https://help.kusto.windows.net",
                extra=json.dumps(
                    {
                        "tenant": "tenant",
                        "auth_method": "AAD_APP",
                    }
                ),
            )
        )
        AzureDataExplorerHook(azure_data_explorer_conn_id=ADX_TEST_CONN_ID)
        assert mock_init.called_with(
            KustoConnectionStringBuilder.with_aad_application_key_authentication(
                "https://help.kusto.windows.net", "app_id", "app key", "tenant"
            )
        )

    @mock.patch.object(KustoClient, "__init__")
    def test_conn_method_aad_app_cert(self, mock_init):
        mock_init.return_value = None
        db.merge_conn(
            Connection(
                conn_id=ADX_TEST_CONN_ID,
                conn_type="azure_data_explorer",
                login="client_id",
                host="https://help.kusto.windows.net",
                extra=json.dumps(
                    {
                        "tenant": "tenant",
                        "auth_method": "AAD_APP_CERT",
                        "certificate": "PEM",
                        "thumbprint": "thumbprint",
                    }
                ),
            )
        )
        AzureDataExplorerHook(azure_data_explorer_conn_id=ADX_TEST_CONN_ID)
        assert mock_init.called_with(
            KustoConnectionStringBuilder.with_aad_application_certificate_authentication(
                "https://help.kusto.windows.net", "client_id", "PEM", "thumbprint", "tenant"
            )
        )

    @mock.patch.object(KustoClient, "__init__")
    def test_conn_method_aad_device(self, mock_init):
        mock_init.return_value = None
        db.merge_conn(
            Connection(
                conn_id=ADX_TEST_CONN_ID,
                conn_type="azure_data_explorer",
                host="https://help.kusto.windows.net",
                extra=json.dumps({"auth_method": "AAD_DEVICE"}),
            )
        )
        AzureDataExplorerHook(azure_data_explorer_conn_id=ADX_TEST_CONN_ID)
        assert mock_init.called_with(
            KustoConnectionStringBuilder.with_aad_device_authentication("https://help.kusto.windows.net")
        )

    @mock.patch.object(KustoClient, "execute")
    def test_run_query(self, mock_execute):
        mock_execute.return_value = None
        db.merge_conn(
            Connection(
                conn_id=ADX_TEST_CONN_ID,
                conn_type="azure_data_explorer",
                host="https://help.kusto.windows.net",
                extra=json.dumps({"auth_method": "AAD_DEVICE"}),
            )
        )
        hook = AzureDataExplorerHook(azure_data_explorer_conn_id=ADX_TEST_CONN_ID)
        hook.run_query("Database", "Logs | schema", options={"option1": "option_value"})
        properties = ClientRequestProperties()
        properties.set_option("option1", "option_value")
        assert mock_execute.called_with("Database", "Logs | schema", properties=properties)

    def test_get_ui_field_behaviour_placeholders(self):
        """
        Check that ensure_prefixes decorator working properly

        Note: remove this test and the _ensure_prefixes decorator after min airflow version >= 2.5.0
        """
        assert list(AzureDataExplorerHook.get_ui_field_behaviour()["placeholders"].keys()) == [
            "login",
            "password",
            "auth_method",
            "tenant",
            "certificate",
            "thumbprint",
        ]
        if get_provider_min_airflow_version("apache-airflow-providers-microsoft-azure") >= (2, 5):
            raise Exception(
                "You must now remove `_ensure_prefixes` from azure utils."
                " The functionality is now taken care of by providers manager."
            )

    @pytest.mark.parametrize(
        "uri",
        [
            param(
                "a://usr:pw@host?extra__azure_data_explorer__tenant=my-tenant"
                "&extra__azure_data_explorer__auth_method=AAD_APP",
                id="prefix",
            ),
            param("a://usr:pw@host?tenant=my-tenant&auth_method=AAD_APP", id="no-prefix"),
        ],
    )
    def test_backcompat_prefix_works(self, uri):
        with patch.dict(os.environ, AIRFLOW_CONN_MY_CONN=uri):
            hook = AzureDataExplorerHook(azure_data_explorer_conn_id="my_conn")  # get_conn is called in init
        assert hook.connection._kcsb.data_source == "host"
        assert hook.connection._kcsb.application_client_id == "usr"
        assert hook.connection._kcsb.application_key == "pw"
        assert hook.connection._kcsb.authority_id == "my-tenant"

    def test_backcompat_prefix_both_causes_warning(self):
        with patch.dict(
            in_dict=os.environ,
            AIRFLOW_CONN_MY_CONN="a://usr:pw@host?tenant=my-tenant&auth_method=AAD_APP"
            "&extra__azure_data_explorer__auth_method=AAD_APP",
        ):
            with pytest.warns(Warning, match="Using value for `auth_method`"):
                hook = AzureDataExplorerHook(azure_data_explorer_conn_id="my_conn")
            assert hook.connection._kcsb.data_source == "host"
            assert hook.connection._kcsb.application_client_id == "usr"
            assert hook.connection._kcsb.application_key == "pw"
            assert hook.connection._kcsb.authority_id == "my-tenant"
