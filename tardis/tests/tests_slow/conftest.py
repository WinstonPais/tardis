import glob
import os
import yaml
import pandas as pd
import pytest

from tardis import __githash__ as tardis_githash
from tardis.tests.tests_slow.report import DokuReport
from tardis.tests.tests_slow.plot_helpers import PlotUploader


def pytest_configure(config):
    integration_tests_configpath = config.getvalue("integration-tests")
    if integration_tests_configpath:
        integration_tests_configpath = os.path.expandvars(
            os.path.expanduser(integration_tests_configpath)
        )
        config.option.integration_tests_config = yaml.load(
            open(integration_tests_configpath))

        if not config.getoption("--generate-reference"):
            # Used by DokuReport class to show build environment details in report.
            config._environment = []
            # prevent opening dokupath on slave nodes (xdist)
            if not hasattr(config, 'slaveinput'):
                config.dokureport = DokuReport(
                    config.option.integration_tests_config['dokuwiki'])
                config.pluginmanager.register(config.dokureport)


def pytest_unconfigure(config):
    # Unregister only if it was registered in pytest_configure
    integration_tests_configpath = config.getvalue("integration-tests")
    if integration_tests_configpath and not config.getoption("--generate-reference"):
        config.pluginmanager.unregister(config.dokureport)


def pytest_terminal_summary(terminalreporter):
    if (terminalreporter.config.getoption("--generate-reference") and
            terminalreporter.config.getvalue("integration-tests")):
        # TODO: Add a check whether generation was successful or not.
        terminalreporter.write_sep("-", "Generated reference data: {0}".format(os.path.join(
            terminalreporter.config.option.integration_tests_config['generate_reference'],
            tardis_githash[:7]
        )))


@pytest.mark.hookwrapper
def pytest_runtest_makereport(item, call):
    # execute all other hooks to obtain the report object
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        if "plot_object" in item.fixturenames:
            plot_obj = item.funcargs["plot_object"]
            plot_obj.upload(report)
            report.extra = plot_obj.get_extras()


@pytest.fixture(scope="function")
def plot_object(request):
    return PlotUploader(request)


@pytest.fixture(scope="class", params=[
    path for path in glob.glob(os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "*")) if os.path.isdir(path)
])
def data_path(request):
    integration_tests_config = request.config.option.integration_tests_config
    hdf_filename = "{0}.h5".format(os.path.basename(request.param))

    path = {
        'config_dirpath': request.param,
        'reference_filepath': os.path.join(os.path.expandvars(
            os.path.expanduser(integration_tests_config["reference"])), hdf_filename
        ),
        'gen_ref_dirpath': os.path.join(os.path.expandvars(os.path.expanduser(
            integration_tests_config["generate_reference"])), tardis_githash[:7]
        ),
        'setup_name': hdf_filename[:-3]
    }
    if (request.config.getoption("--generate-reference") and not
            os.path.exists(path['gen_ref_dirpath'])):
        os.makedirs(path['gen_ref_dirpath'])
    return path


@pytest.fixture(scope="class")
def reference(request, data_path):
    """Fixture to ingest reference data for slow test from already available
    HDF file. All data is unpacked as a collection of ``pd.Series`` and
    ``pd.DataFrames`` in a ``pd.HDFStore`` object and returned away.

    Assumed that ``data_path['reference_filepath']`` is a valid HDF file
    containing the reference dath for a particular setup.
    """
    # Reference data need not be loaded and provided if current test run itself
    # generates new reference data.
    if request.config.getoption("--generate-reference"):
        return
    return pd.HDFStore(data_path['reference_filepath'])
