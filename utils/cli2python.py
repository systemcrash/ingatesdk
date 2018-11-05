#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import re
import argparse

from ingate import parser

pycode_tmpl = """#!/usr/bin/python
# -*- coding: utf-8 -*-

import json
from ingate import ingatesdk

version = 'v1'
scheme = 'http'
user = 'alice'
password = 'foobar'
address = '192.168.1.1'
port = ''

%(certificates)s

# Create API client.
api_client = ingatesdk.Client(version, scheme, address, user, password,
                              port=port)

# Authenticate and get hold of a security token.
print('Authenticate and get hold of a security token')
response = api_client.authenticate()
print(json.dumps(response, indent=4, separators=(',', ': ')))
print('')

%(generated)s
"""

valid_table = re.compile(r'^[A-Za-z0-9_]+\.[A-Za-z0-9_]+$')
valid_rowid = re.compile(r'^[0-9]+$')
filter_columns = [('network.interfaces', 'autoneg')]


def escape_string(value):
    escape_value = value.replace('\\', '\\\\')
    escape_value = escape_value.replace('"', '\\"')
    return escape_value


def escape_quotes(value):
    escape_value = value.replace('"', '\\"')
    return escape_value


def escape_singe_quotes(value):
    escape_value = value.replace("'", "\\'")
    return escape_value


def demangle_ipsec_secret(value):
    # psk
    if value.startswith('s'):
        return value[1:]
    # x509ca
    elif value.startswith('a'):
        return value[1:]
    # x509ca_dn
    elif value.startswith('c'):
        return value[1:]
    # xauth_psk
    elif value.startswith('p'):
        return value[1:]
    else:
        return value


def clear_table(line, noquotes=[]):
    clicmd = line.split(' ')
    table = None
    for part in clicmd[1:]:
        if valid_table.match(part):
            table = part
            break
    if not table:
        print('Cannot find table name')
        sys.exit(-1)

    response = '# %s\n' % line
    response += 'print(\'%s\')\n' % (escape_singe_quotes(line))
    response += 'response = api_client.delete_table(\'%s\')\n' % table
    response += ('print(json.dumps(response, indent=4,'
                 ' separators=(\',\', \': \')))\n')
    response += 'print(\'\')\n\n'
    return response


def load_factory(line, noquotes=[]):
    response = '# %s\n' % line
    response += 'print(\'%s\')\n' % (escape_singe_quotes(line))
    response += 'response = api_client.load_factory()\n'
    response += ('print(json.dumps(response, indent=4,'
                 ' separators=(\',\', \': \')))\n')
    response += 'print(\'\')\n\n'
    return response


def add_row(line, noquotes=[]):
    line = r'%s' % line
    line = unicode(line)
    cli_parser = parser.Parser(line)
    cli_parser.do_parse()

    clicmd = line.split(' ')
    table = None
    for part in clicmd[1:]:
        if valid_table.match(part):
            table = part
    if not table:
        print('Cannot find table name')
        sys.exit(-1)

    assignments = cli_parser.assignments()
    column_values = []
    for column, value in assignments.items():
        if (table, column) in filter_columns:
            continue
        if table == 'ipsec.peers' and column == 'secret':
            value = demangle_ipsec_secret(value)
        if column in noquotes:
            column_values.append("%s=%s" % (column, escape_string(value)))
        else:
            column_values.append("%s=\"%s\"" % (column, escape_string(value)))
    if not column_values:
        print('Cannot find column values')
        sys.exit(-1)

    response = '# %s\n' % line
    response += 'print(\'%s\')\n' % (escape_singe_quotes(line))
    add_row_line = 'response = api_client.add_row("%s", %s)\n'
    response += add_row_line % (table, ', '.join(column_values))
    response += ('print(json.dumps(response, indent=4,'
                 ' separators=(\',\', \': \')))\n')
    response += 'print(\'\')\n\n'
    return response


def modify_row(line, noquotes=[]):
    line = r'%s' % line
    line = unicode(line)
    cli_parser = parser.Parser(line)
    cli_parser.do_parse()

    clicmd = line.split(' ')
    table = None
    rowid = None
    for part in clicmd[1:]:
        if valid_table.match(part):
            table = part
        if valid_rowid.match(part):
            rowid = part
        if table and rowid:
            break
    if not table:
        print('Cannot find table name')
        sys.exit(-1)
    if not rowid:
        print('Cannot find rowid')
        sys.exit(-1)

    assignments = cli_parser.assignments()
    column_values = []
    for column, value in assignments.items():
        if (table, column) in filter_columns:
            continue
        if table == 'ipsec.peers' and column == 'secret':
            value = demangle_ipsec_secret(value)
        if column in noquotes:
            column_values.append("%s=%s" % (column, escape_string(value)))
        else:
            column_values.append("%s=\"%s\"" % (column, escape_string(value)))
    if not column_values:
        print('Cannot find column values')
        sys.exit(-1)

    response = '# %s\n' % line
    response += 'print(\'%s\')\n' % (escape_singe_quotes(line))
    modify_row_line = 'response = api_client.modify_row("%s", rowid=%s, %s)\n'
    response += modify_row_line % (table, rowid, ', '.join(column_values))
    response += ('print(json.dumps(response, indent=4,'
                 ' separators=(\',\', \': \')))\n')
    response += 'print(\'\')\n\n'
    return response


def generate_py_cert(certs):
    response = []

    for name, certs in certs.items():
        line = '%s = """\n' % name
        for cert in certs:
            # IPsec X509 Peer certificate. Remove prefix 'x'.
            if cert.startswith('x'):
                cert = cert[1:]
            line += cert
        line += '"""'
        response.append(line)
    return response

begin_cert = '-----BEGIN CERTIFICATE-----'
end_cert = '-----END CERTIFICATE-----'
begin_x509_crl = '-----BEGIN X509 CRL-----'
end_x509_crl = '-----END X509 CRL-----'
begin_private = '-----BEGIN PRIVATE KEY-----'
end_private = '-----END PRIVATE KEY-----'
begin_cert_req = '-----BEGIN CERTIFICATE REQUEST-----'
end_cert_req = '-----END CERTIFICATE REQUEST-----'

keywords = {
    'clear-table': (clear_table),
    'add-row': (add_row),
    'load-factory': (load_factory),
    'modify-row': (modify_row),
}


def main(argv):
    parser = (argparse.
              ArgumentParser(description='Generate Python code from Ingate CLI'
                             ' backup file.'))
    parser.add_argument('infile',
                        help='The CLI file to convert.')
    parser.add_argument('--outfile',
                        help='Name of the output python file. If omitted the'
                        ' name will be \"infile\".py')
    args = parser.parse_args()

    with open(args.infile, 'r') as inp:
        cli_file = inp.read()

    pycode = ''
    prevline = None
    begin_cert_state = False
    begin_x509_crl_state = False
    begin_private_state = False
    begin_cert_req_state = False
    cert_data = ''
    certs = {}
    cert_counter = 0
    no_quotes = []

    for line in cli_file.splitlines():
        line = line.decode('utf-8').strip()
        if len(line) == 0 or line.startswith('#'):
            continue
        if line.startswith('" \\'):
            line = '\\'

        # Certificate
        if begin_cert in line:
            begin_cert_state = True
            cert_data = line + '\n'
            continue
        if begin_cert_state and end_cert not in line:
            cert_data += line + '\n'
            continue
        if end_cert in line:
            begin_cert_state = False
            cert_data += line + '\n'
            if not cert_data.startswith(begin_cert):
                cert_counter += 1
                cert_name = 'CERT_BLOB_%d' % (cert_counter)
                (certs.setdefault(cert_name, []).
                 append(cert_data.split('=', 1)[1][1:]))
                no_quotes.append(cert_data.split('=')[0])
                prevline += cert_data.split('=')[0] + '=' + cert_name + ' '
            else:
                cert_name = 'CERT_BLOB_%d' % (cert_counter)
                certs.setdefault(cert_name, []).append(cert_data)
            continue

        # Certificate Request
        if begin_cert_req in line:
            begin_cert_req_state = True
            cert_data = line + '\n'
            continue
        if begin_cert_req_state and end_cert_req not in line:
            cert_data += line + '\n'
            continue
        if end_cert_req in line:
            begin_cert_req_state = False
            cert_data += line + '\n'
            cert_counter += 1
            cert_name = 'CERT_BLOB_%d' % (cert_counter)
            (certs.setdefault(cert_name, []).
             append(cert_data.split('=', 1)[1][1:]))
            no_quotes.append(cert_data.split('=')[0])
            prevline += cert_data.split('=')[0] + '=' + cert_name + ' '
            continue

        # Private key
        if begin_private in line:
            begin_private_state = True
            cert_data = line + '\n'
            continue
        if begin_private_state and end_private not in line:
            cert_data += line + '\n'
            continue
        if end_private in line:
            begin_private_state = False
            cert_data += line + '\n'
            cert_counter += 1
            cert_name = 'CERT_BLOB_%d' % (cert_counter)
            (certs.setdefault(cert_name, []).
             append(cert_data.split('=', 1)[1][1:]))
            no_quotes.append(cert_data.split('=')[0])
            prevline += cert_data.split('=')[0] + '=' + cert_name + ' '
            continue

        # CRL
        if begin_x509_crl in line:
            begin_x509_crl_state = True
            cert_data = line + '\n'
            continue
        if begin_x509_crl_state and end_x509_crl not in line:
            cert_data += line + '\n'
            continue
        if end_x509_crl in line:
            begin_x509_crl_state = False
            cert_data += line + '\n'
            cert_counter += 1
            cert_name = 'CERT_BLOB_%d' % (cert_counter)
            (certs.setdefault(cert_name, []).
             append(cert_data.split('=', 1)[1][1:]))
            no_quotes.append(cert_data.split('=')[0])
            prevline += cert_data.split('=')[0] + '=' + cert_name
            continue

        if line.endswith('\\'):
            line = line.rstrip('\\')
            if prevline:
                prevline = prevline + ' ' + line
            else:
                prevline = line
            continue

        if prevline:
            outline = prevline + ' ' + line
            prevline = None
        else:
            outline = line

        cmd_name = outline.split(' ', 1)[0]
        command_info = keywords.get(cmd_name)
        if not command_info:
            print('Cannot find table command %s' % (cmd_name))
            sys.exit(-1)
        cmdfunc = command_info
        response = cmdfunc(outline, no_quotes)
        pycode += response
        no_quotes = []

    certificates = generate_py_cert(certs)
    if args.outfile:
        outfile = args.outfile
    else:
        outfile = args.infile + '.py'

    with open(outfile, 'w') as outp:
        data = pycode_tmpl % {'generated': pycode.rstrip('\n'),
                              'certificates': '\n\n'.join(certificates)}
        outp.write(data.encode('utf-8'))
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))