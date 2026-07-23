# encoding: utf-8

import pytest

import ckanext.dataexplorer.plugin as plugin


class TestReclineViewInfo(object):
    '''Unit tests for the view ``info`` schemas and ``can_view`` logic.

    These do not require a database or a running app.
    '''

    def test_dataexplorer_has_no_schema(self):
        view = plugin.ReclineView()
        assert view.info().get('schema') is None

    def test_grid_view_has_no_schema(self):
        view = plugin.ReclineGridView()
        assert view.info().get('schema') is None

    def test_graph_view_has_the_correct_schema_keys(self):
        view = plugin.ReclineGraphView()
        schema = view.info().get('schema')
        expected_keys = ['offset', 'limit', 'graph_type', 'group', 'series']
        _assert_schema_exists_and_has_keys(schema, expected_keys)

    def test_map_view_has_the_correct_schema_keys(self):
        view = plugin.ReclineMapView()
        schema = view.info().get('schema')
        expected_keys = ['offset', 'limit', 'map_field_type',
                         'latitude_field', 'longitude_field', 'geojson_field',
                         'auto_zoom', 'cluster_markers']
        _assert_schema_exists_and_has_keys(schema, expected_keys)


class TestReclineViewCanView(object):
    '''Unit tests for ``can_view``.'''

    def test_base_can_view_datastore_active(self):
        view = plugin.ReclineGridView()

        assert view.can_view({'resource': {'datastore_active': True}})
        assert not view.can_view({'resource': {'datastore_active': False}})

    def test_dataexplorer_can_view_datastore_active(self):
        view = plugin.ReclineView()

        assert view.can_view({'resource': {'datastore_active': True}})

    def test_dataexplorer_can_view_supported_formats_without_datastore(self):
        '''Supported file formats are viewable even without the datastore.'''
        view = plugin.ReclineView()
        formats = ['CSV', 'XLS', 'XLSX', 'TSV', 'csv', 'xls', 'xlsx', 'tsv']
        for resource_format in formats:
            data_dict = {'resource': {'datastore_active': False,
                                      'format': resource_format}}
            assert view.can_view(data_dict), resource_format

    def test_dataexplorer_cannot_view_unsupported_formats(self):
        view = plugin.ReclineView()
        formats = ['TXT', 'txt', 'doc', 'JSON']
        for resource_format in formats:
            data_dict = {'resource': {'datastore_active': False,
                                      'format': resource_format}}
            assert not view.can_view(data_dict), resource_format


@pytest.mark.ckan_config('ckan.plugins', 'dataexplorer datastore')
@pytest.mark.usefixtures('with_plugins', 'clean_db', 'clean_index')
class TestReclineViewDatastore(object):
    '''Functional test that renders a Data Explorer view for a datastore
    resource. Requires a database and Solr index.
    '''

    def test_create_datastore_only_view(self, app):
        from ckan.tests import helpers, factories

        dataset = factories.Dataset()
        data = {
            'resource': {'package_id': dataset['id']},
            'fields': [{'id': 'a'}, {'id': 'b'}],
            'records': [{'a': 1, 'b': 'xyz'}, {'a': 2, 'b': 'zzz'}],
        }
        result = helpers.call_action('datastore_create', **data)
        resource_id = result['resource_id']

        resource_view = helpers.call_action(
            'resource_view_create',
            resource_id=resource_id,
            view_type='dataexplorer',
            title='Test View',
            description='A nice test view',
        )

        url = plugin.toolkit.url_for(
            'resource.read',
            id=dataset['id'],
            resource_id=resource_id,
        )
        response = app.get(url)
        assert resource_view['title'] in response.body


def _assert_schema_exists_and_has_keys(schema, expected_keys):
    assert schema is not None, schema

    keys = sorted(schema.keys())
    expected_keys = sorted(expected_keys)

    assert keys == expected_keys, '%s != %s' % (keys, expected_keys)
