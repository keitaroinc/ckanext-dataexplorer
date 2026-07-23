import logging
import json
import csv
from io import StringIO, BytesIO

from flask import Response

import ckan.logic as logic
from ckan.common import config, _
from xml.etree.ElementTree import Element, SubElement, ElementTree
from ckanext.dataexplorer.helpers import (CustomJSONEncoder,
                                          remove_elements,
                                          replace)


DUMP_FORMATS = 'csv', 'json', 'xml', 'tsv'

UTF8_BOM = u'\uFEFF'.encode(u'utf-8')

log = logging.getLogger(__name__)


class XMLWriter(object):
    def __init__(self, columns, data):
        self.output = BytesIO()
        self.delimiter = config.get(
            'ckanext.dataexplorer.headers_names_delimiter', "_")
        columns_fixed = []
        for column in columns:
            columns_fixed.append(replace(column))
        self.columns = columns_fixed
        self.n = len(data)
        self.output.write(b'<data>\n')

    def writerow(self, data):
        for index, row in enumerate(data):
            remove_elements(row)
            root = Element('row')
            for k, v in zip(self.columns, row.values()):
                if v is None:
                    SubElement(root, k).text = u'NULL'
                    continue
                SubElement(root, k).text = str(v)
            ElementTree(root).write(self.output, encoding='utf-8')
            self.output.write(b'\n')
            if index == (self.n - 1):
                self.output.write(b'</data>\n')
            yield self.output.getvalue()
            self.output.truncate(0)
            self.output.seek(0)


class JSONWriter(object):
    def __init__(self, columns, data):
        self.output = StringIO()
        self.columns = columns
        self.first = True
        self.n = len(data)
        self.output.write(
            '{\n  "fields": %s,\n  "records": [' %
            json.dumps(columns, ensure_ascii=False, separators=(',', ':')))

    def writerow(self, data):
        for index, json_line in enumerate(data):
            remove_elements(json_line)
            if self.first:
                self.first = False
                self.output.write('\n  ')
            else:
                self.output.write(',\n  ')
            self.output.write(json.dumps(
                    json_line,
                    ensure_ascii=False,
                    separators=(u',', u':'),
                    sort_keys=True,
                    cls=CustomJSONEncoder))
            if index == (self.n - 1):
                self.finish()
            yield self.output.getvalue()
            self.output.truncate(0)
            self.output.seek(0)

    def finish(self):
        self.output.write('\n]}\n')


class UnicodeCSVWriter:
    """
    A CSV writer which will write rows to CSV file
    """

    def iter_csv(columns, data, delimiter=','):
        line = StringIO()
        writer = csv.writer(line, delimiter=delimiter)
        writer.writerow(columns)
        for csv_line in data:
            remove_elements(csv_line)
            csv_line = csv_line.values()
            writer.writerow(csv_line)
            line.seek(0)
            yield line.read()
            line.truncate(0)
            line.seek(0)


class FileWriterService():
    def _tsv_writer(self, columns, records, name):
        response = Response(UnicodeCSVWriter.iter_csv(columns,
                                                      records,
                                                      delimiter='\t'),
                            mimetype='text/csv')
        response.headers['Content-Type'] = 'text/tsv; charset=utf-8'
        if name:
            response.headers['Content-disposition'] = \
                'attachment; filename="{name}.tsv"'.format(name=name)

        return response

    def _csv_writer(self, columns, records, name):
        response = Response(UnicodeCSVWriter.iter_csv(columns,
                                                      records,
                                                      delimiter=','),
                            mimetype='text/csv')
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        if name:
            response.headers['Content-disposition'] = \
                'attachment; filename="{name}.csv"'.format(name=name)

        return response

    def _json_writer(self, columns, records, name):
        json_obj = JSONWriter(columns, records)
        response = Response(json_obj.writerow(records),
                            mimetype='application/json')

        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        if name:
            response.headers['Content-disposition'] = \
                'attachment; filename="{name}.json"'.format(name=name)

        return response

    def _xml_writer(self, columns, records, name):
        xml_obj = XMLWriter(columns, records)
        response = Response(xml_obj.writerow(records),
                            mimetype='text/xml')
        response.headers['Content-Type'] = 'text/xml; charset=utf-8'
        if name:
            response.headers['Content-disposition'] = \
                'attachment; filename="{name}.xml"'.format(name=name)

        return response

    def _xlsx_writer(self, columns, records, response, name):
        # Imported lazily so a missing/incompatible XlsxWriter never prevents
        # the plugin (and therefore CKAN) from starting.
        from xlsxwriter.workbook import Workbook

        output = BytesIO()

        if hasattr(response, u'headers'):
            response.headers['Content-Type'] = (
                'application/vnd.openxmlformats-officedocument'
                '.spreadsheetml.sheet; charset=utf-8')
            if name:
                response.headers['Content-disposition'] = \
                    'attachment; filename="{name}.xlsx"'.format(name=name)

        workbook = Workbook(output)
        worksheet = workbook.add_worksheet()

        # Writing headers
        col = 0
        for c in columns:
            worksheet.write(0, col, c)
            col += 1

        # Writing records
        row = 1
        for record in records:
            col = 0
            for column in columns:
                worksheet.write(row, col, record[column])
                col += 1
            row += 1

        workbook.close()
        response.write(output.getvalue())

    def write_to_file(self, columns, records, format, name):

        format = format.lower()
        if format == 'csv':
            return self._csv_writer(columns, records, name)
        if format == 'json':
            return self._json_writer(columns, records, name)
        if format == 'xml':
            return self._xml_writer(columns, records, name)
        if format == 'tsv':
            return self._tsv_writer(columns, records, name)
        raise logic.ValidationError(_(
            u'format: must be one of %s') % u', '.join(DUMP_FORMATS))
