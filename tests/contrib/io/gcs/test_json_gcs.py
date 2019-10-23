# Copyright 2018-2019 QuantumBlack Visual Analytics Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
# NONINFRINGEMENT. IN NO EVENT WILL THE LICENSOR OR OTHER CONTRIBUTORS
# BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF, OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# The QuantumBlack Visual Analytics Limited ("QuantumBlack") name and logo
# (either separately or in combination, "QuantumBlack Trademarks") are
# trademarks of QuantumBlack. The License does not grant you any right or
# license to the QuantumBlack Trademarks. You may not use the QuantumBlack
# Trademarks or any confusingly similar mark as a trademark for your product,
#     or use the QuantumBlack Trademarks in any other manner that might cause
# confusion in the marketplace, including but not limited to in advertising,
# on websites, or on software.
#
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=protected-access
import os

import google.auth.credentials
import mock
import pandas as pd
import pytest
import vcr
from pandas.util.testing import assert_frame_equal

from kedro.contrib.io.gcs.json_gcs import JSONGCSDataSet
from kedro.io import DataSetError, Version
from tests.contrib.io.gcs.utils import matcher

FILENAME = "test.json"
BUCKET_NAME = "testbucketkedro"
GCP_PROJECT = "test_project"
GCP_CREDENTIALS = mock.Mock(spec=google.auth.credentials.Credentials)

api_records_path = os.path.join(os.path.dirname(__file__), "api_recordings/json")

gcs_vcr = vcr.VCR(
    cassette_library_dir=api_records_path,
    path_transformer=vcr.VCR.ensure_suffix(".yaml"),
    filter_headers=["Authorization"],
    filter_query_parameters=["refresh_token", "client_id", "client_secret"],
)
gcs_vcr.register_matcher("all", matcher)
gcs_vcr.match_on = ["all"]


@pytest.fixture
def dummy_dataframe():
    return pd.DataFrame({"col1": [1, 2], "col2": [4, 5], "col3": [5, 6]})


@pytest.fixture(params=[None])
def load_args(request):
    return request.param


@pytest.fixture(params=[None])
def save_args(request):
    return request.param


@pytest.fixture
def gcs_data_set(load_args, save_args):
    return JSONGCSDataSet(
        filepath=FILENAME,
        bucket_name=BUCKET_NAME,
        project=GCP_PROJECT,
        credentials=GCP_CREDENTIALS,
        load_args=load_args,
        save_args=save_args,
    )


class TestJsonGCSDataSet:
    @mock.patch.dict(
        os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "wrong credentials"}
    )
    def test_invalid_credentials(self):
        """Test invalid credentials for connecting to GCS"""
        pattern = "Anonymous caller"
        with pytest.raises(DataSetError, match=pattern):
            JSONGCSDataSet(filepath=FILENAME, bucket_name=BUCKET_NAME).load()

    @gcs_vcr.use_cassette(match=["api_recordings/json/*.yaml"])
    def test_not_existing_bucket(self):
        """Test not existing bucket"""
        pattern = r"Failed while loading data from data set JSONGCSDataSet\(.+\)"

        with pytest.raises(DataSetError, match=pattern):
            JSONGCSDataSet(
                filepath=FILENAME,
                bucket_name="not-existing-bucket",
                credentials=GCP_CREDENTIALS,
            ).load()

    @gcs_vcr.use_cassette(match=["api_recordings/json/*.yaml"])
    def test_save_data(self, gcs_data_set, dummy_dataframe):
        """Test saving the data"""
        assert not gcs_data_set.exists()
        gcs_data_set.save(dummy_dataframe)
        loaded_data = gcs_data_set.load()
        assert_frame_equal(loaded_data, dummy_dataframe)

    @gcs_vcr.use_cassette(match=["api_recordings/json/*.yaml"])
    def test_load_data(self, gcs_data_set, dummy_dataframe):
        """Test loading the data from gcs."""
        loaded_data = gcs_data_set.load()
        assert_frame_equal(loaded_data, dummy_dataframe)

    @gcs_vcr.use_cassette(match=["api_recordings/json/*.yaml"])
    def test_exists(self, gcs_data_set, dummy_dataframe):
        """Test `exists` method invocation for both existing and
        nonexistent data set."""
        assert not gcs_data_set.exists()
        gcs_data_set.save(dummy_dataframe)
        assert gcs_data_set.exists()

    def test_load_save_args(self, gcs_data_set):
        """Test default load and save arguments of the data set."""
        assert not gcs_data_set._load_args
        assert "index" in gcs_data_set._save_args

    @pytest.mark.parametrize(
        "load_args", [{"k1": "v1", "index": "value"}], indirect=True
    )
    def test_load_extra_params(self, gcs_data_set, load_args):
        """Test overriding the default load arguments."""
        for key, value in load_args.items():
            assert gcs_data_set._load_args[key] == value

    @pytest.mark.parametrize(
        "save_args", [{"k1": "v1", "index": "value"}], indirect=True
    )
    def test_save_extra_params(self, gcs_data_set, save_args):
        """Test overriding the default save arguments."""
        save_args = {"k1": "v1", "index": "value"}
        for key, value in save_args.items():
            assert gcs_data_set._save_args[key] == value

    @pytest.mark.parametrize("save_args", [{"option": "value"}], indirect=True)
    def test_str_representation(self, gcs_data_set, save_args):
        """Test string representation of the data set instance."""
        str_repr = str(gcs_data_set)
        assert "JsonGCSDataSet" in str_repr
        for k in save_args.keys():
            assert k in str_repr

    # pylint: disable=unused-argument
    @gcs_vcr.use_cassette(match=["api_recordings/json/*.yaml"])
    def test_load_args_propagated(self, mocker, gcs_data_set):
        mock = mocker.patch("kedro.contrib.io.gcs.json_gcs.pd.read_json")
        JSONGCSDataSet(
            filepath=FILENAME,
            bucket_name=BUCKET_NAME,
            credentials=GCP_CREDENTIALS,
            load_args=dict(custom=42),
        ).load()
        assert mock.call_args_list[0][1] == {"custom": 42}


@pytest.fixture
def versioned_gcs_data_set(load_version, save_version, load_args, save_args):
    return JSONGCSDataSet(
        bucket_name=BUCKET_NAME,
        filepath=FILENAME,
        project=GCP_PROJECT,
        credentials=GCP_CREDENTIALS,
        load_args=load_args,
        save_args=save_args,
        version=Version(load_version, save_version),
    )


class TestJsonGCSDataSetVersioned:
    @gcs_vcr.use_cassette(match=["api_recordings/json/*.yaml"])
    def test_no_versions(self, versioned_gcs_data_set):
        """Check the error if no versions are available for load."""
        pattern = r"Did not find any versions for JSONGCSDataSet\(.+\)"
        with pytest.raises(DataSetError, match=pattern):
            versioned_gcs_data_set.load()

    @gcs_vcr.use_cassette(match=["api_recordings/json/*.yaml"])
    @pytest.mark.parametrize(
        "save_version", ["2019-01-02T00.00.00.000Z"], indirect=True
    )
    def test_save_and_load(self, versioned_gcs_data_set, dummy_dataframe):
        """Test that saved and reloaded data matches the original one for
        the versioned data set."""
        versioned_gcs_data_set.save(dummy_dataframe)
        reloaded_df = versioned_gcs_data_set.load()
        assert_frame_equal(dummy_dataframe, reloaded_df)

    @gcs_vcr.use_cassette(match=["api_recordings/json/*.yaml"])
    @pytest.mark.parametrize(
        "save_version", ["2019-01-02T00.00.00.000Z"], indirect=True
    )
    def test_prevent_override(self, versioned_gcs_data_set, dummy_dataframe):
        """Check the error when attempting to override the data set if the
        corresponding pickled object for a given save version already exists in S3."""
        versioned_gcs_data_set.save(dummy_dataframe)
        pattern = (
            r"Save path \`.+\` for JsonGCSDataSet\(.+\) must not exist "
            r"if versioning is enabled"
        )
        with pytest.raises(DataSetError, match=pattern):
            versioned_gcs_data_set.save(dummy_dataframe)

    @pytest.mark.parametrize(
        "load_version", ["2019-01-01T23.59.59.999Z"], indirect=True
    )
    @pytest.mark.parametrize(
        "save_version", ["2019-01-02T00.00.00.000Z"], indirect=True
    )
    @gcs_vcr.use_cassette(match=["api_recordings/json/*.yaml"])
    def test_save_version_warning(
        self, versioned_gcs_data_set, load_version, save_version, dummy_dataframe
    ):
        """Check the warning when saving to the path that differs from
        the subsequent load path."""
        pattern = (
            r"Save path `.*/{}/test\.json` did not match load path "
            r"`.*/{}/test\.json` for JsonGCSDataSet\(.+\)".format(
                save_version, load_version
            )
        )
        with pytest.warns(UserWarning, match=pattern):
            versioned_gcs_data_set.save(dummy_dataframe)

    def test_version_str_repr(self, load_version, save_version):
        """Test that version is in string representation of the class instance
        when applicable."""
        ds = JSONGCSDataSet(filepath=FILENAME, bucket_name=BUCKET_NAME)
        ds_versioned = JSONGCSDataSet(
            filepath=FILENAME,
            bucket_name=BUCKET_NAME,
            version=Version(load_version, save_version),
        )
        assert FILENAME in str(ds)
        assert "version" not in str(ds)

        assert FILENAME in str(ds_versioned)
        ver_str = "version=Version(load={}, save='{}')".format(
            load_version, save_version
        )
        assert ver_str in str(ds_versioned)

        assert BUCKET_NAME in str(ds)
        assert BUCKET_NAME in str(ds_versioned)

    @gcs_vcr.use_cassette(match=["api_recordings/json/*.yaml"])
    @pytest.mark.parametrize(
        "save_version", ["2019-01-02T00.00.00.000Z"], indirect=True
    )
    def test_existed_versioned(self, versioned_gcs_data_set, dummy_dataframe):
        """Test `exists` method invocation for versioned data set."""
        assert not versioned_gcs_data_set.exists()
        versioned_gcs_data_set.save(dummy_dataframe)
        assert versioned_gcs_data_set.exists()
