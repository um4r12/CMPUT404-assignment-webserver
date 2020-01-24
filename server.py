#  coding: utf-8
import socketserver
import urllib.parse
import posixpath
import os
import mimetypes

# Copyright 2013 Abram Hindle, Eddie Antonio Santos
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
# Furthermore it is derived from the Python documentation examples thus
# some of the code is Copyright © 2001-2013 Python Software
# Foundation; All Rights Reserved
#
# http://docs.python.org/2/library/socketserver.html
#
# run: python freetests.py

# try: curl -v -X GET http://127.0.0.1:8080/

HOST, PORT = "127.0.0.1", 8080


class MyWebServer(socketserver.BaseRequestHandler):

    HTTP_MAJOR_MINOR = ["1", "1"]
    SERVER_PROTOCOL = "HTTP" + "/" + ".".join(HTTP_MAJOR_MINOR)
    DEFAULT_AUTHORITY = str(HOST) + ":" + str(PORT)
    DEFAULT_ERROR_HTML = '''<!DOCTYPE HTML>
<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html;charset=utf-8">
        <title>Error response</title>
    </head>
    <body>
        <h1>Error response</h1>
        <p>Error code: %s</p>
        <p>Message: %s.</p>
        <p>Error code explanation: %s - %s.</p>
    </body>
</html>'''
    DEFAULT_LISTDIR_HTML = '''<!DOCTYPE HTML>
<html>
<head>
    <title>Directory listing</title>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
</head>
<body>
    <h1>Directory structure</h1>
    <hr>
    <ul>
        %s
    </ul>
    <hr>
</body>
</html>'''
    UL_HTML = '''<li><a href="%s">%s</a></li>\n\t\t'''
    RESPONSES = {
        200: ('OK', 'Request fulfilled, document follows'),
        301: ('Moved Permanently', 'Object moved permanently -- see URI list'),
        400: ('Bad Request',
              'Bad request syntax or unsupported method'),
        404: ('Not Found', 'Nothing matches the given URI'),
        405: ('Method Not Allowed',
              'Specified method is invalid for this resource.'),
        500: ('Internal Server Error', 'Server got itself in trouble')
        }

    VHOSTS = {DEFAULT_AUTHORITY: "www"}

    def handle(self):

        self.close_connection = True
        self.handle_one_request()
        # while not self.close_connection:
        #     self.handle_one_request()

    def handle_one_request(self):

        self.raw_request = self.request.recv(1024).strip().decode()
        self.raw_request_crlf_rm = self.raw_request.split("\r\n")
        self.response_headers = []

        if not self.parse_request():
            return

        func_name = "do_" + self.request_method
        if not hasattr(self, func_name):
            self.send_error(405, self.RESPONSES[405])
            return False
        func = getattr(self, func_name)
        func()

    def parse_request(self):

        # parse out request_method, request_uri, request_SERVER_PROTOCOL,
        # request_headers, and any body
        # return True if success, False is failure to parse &
        # send appropriate error code

        self.request_method = None
        self.uri = ""
        self.request_headers = {}
        self.vhost_root_dir = self.VHOSTS[self.DEFAULT_AUTHORITY]

        request_line = self.raw_request_crlf_rm[0].split(" ")
        req_line_arg_len = len(request_line)
        req_maj = 0
        req_min = 9

        if req_line_arg_len == 0:
            return False
        elif req_line_arg_len < 2 or req_line_arg_len > 3:
            self.send_error(400, self.RESPONSES[400])
            return False
        elif req_line_arg_len == 3:
            ver = request_line[-1]
            if not ("." in ver and ver.startswith("HTTP/")):
                self.send_error(400, self.RESPONSES[400])
                return False
            req_maj, req_min = list(map(int, ver.split("/")[-1].split(".")))
            if req_maj > 1:
                self.send_error(505, self.RESPONSES[505])
                return False
            if req_maj == 1 and req_min > 0:
                self.close_connection = False

        self.client_protocol = "HTTP/" + ".".join([str(req_maj), str(req_min)])

        self.request_method = request_line[0].upper()

        uri = request_line[1]
        uri = uri.split("?")[0].split("#")[0]
        trailing_slash = uri.endswith("/")
        uri = urllib.parse.unquote(uri)
        uri = posixpath.normpath(uri)
        remove = ["", ".", ".."]
        for node in uri.split("/"):
            if node not in remove:
                if not self.uri:
                    self.uri = node
                else:
                    self.uri = os.path.join(self.uri, node)
        if trailing_slash:
            self.uri += "/"

        # parse headers
        if not self.parse_request_headers():
            self.send_error(400, self.RESPONSES[400])
            return False

        # check if host field is present, false if http/1.1 >=
        vhost = self.get_header("host")
        if not vhost and req_maj >= 1 and req_min >= 1:
            self.send_error(400, self.RESPONSES[400])
            return False
        elif vhost in self.VHOSTS:
            self.vhost_root_dir = self.VHOSTS[vhost]

        connection = self.get_header("connection")
        if connection == "close":
            self.close_connection = True

        return True

    def parse_request_headers(self):
        for header in self.raw_request_crlf_rm[1:]:
            if header == "":
                break
            try:
                header_key, header_value = header.split(":", 1)
                header_key = header_key.strip().lower()
                header_value = header_value.strip().lower()
                self.request_headers[header_key] = header_value
            except ValueError:
                return False
        return True

    def do_GET(self):
        message_body = None

        vhost_uri = "/".join([self.vhost_root_dir, self.uri])

        # 301 redirection
        if not vhost_uri.endswith("/") and os.path.isdir(vhost_uri):
            authority = "http://" + self.DEFAULT_AUTHORITY
            redirection_uri = os.path.join(authority, self.uri, "")
            self.add_header("Location", redirection_uri)
            self.send_error(301, self.RESPONSES[301])
            return

        # Assume uri of a directory refers to index.html if it exists
        # otherwise list directory content

        if not os.path.exists(vhost_uri):
            self.send_error(404, self.RESPONSES[404])
            return

        if os.path.isdir(vhost_uri):
            if os.path.isfile(os.path.join(vhost_uri, "index.html")):
                vhost_uri = os.path.join(vhost_uri, "index.html")
                # list directory
            else:
                dir_html = ""
                for entity in os.listdir(vhost_uri):
                    if os.path.isdir(os.path.join(vhost_uri, entity)):
                        entity = entity + "/"
                    quoted_entity = urllib.parse.quote(entity)
                    dir_html += self.UL_HTML % (quoted_entity, entity)
                message_body = self.DEFAULT_LISTDIR_HTML % dir_html
                self.add_header("Content-Type", "text/html")

        if os.path.isfile(vhost_uri):
            f = open(vhost_uri, "r")
            message_body = f.read()
            mime_type = mimetypes.guess_type(vhost_uri)[0]
            self.add_header("Content-Type", mime_type)

        self.send_response("200", "OK", message_body)

    def send_error(self, error_code, error_message):

        short_desc, long_desc = error_message
        message_body = self.DEFAULT_ERROR_HTML % (error_code, short_desc,
                                                  error_code, long_desc)
        self.add_header("Content-Type", "text/html")
        self.send_response(error_code, short_desc, message_body)

    def send_response(self, status_code, status_desc, message_body=None):

        status_line_parts = [str(self.SERVER_PROTOCOL), str(status_code),
                             str(status_desc)]
        status_line = " ".join(status_line_parts)
        content_len = len(message_body.encode("utf-8")) if message_body else 0

        # add standard headers
        self.add_header("Content-Length", content_len)
        # add server details
        # add datestamp

        response_headers = "\r\n".join(self.response_headers) + "\r\n"

        send = [status_line, response_headers]

        if message_body:
            send.append(message_body)

        response = "\r\n".join(send).encode("utf-8")
        self.request.sendall(bytearray(response))

    def add_header(self, keyword, value):
        self.response_headers.append("%s: %s" % (keyword, value))

    def get_header(self, header):
        if header in self.request_headers:
            return self.request_headers[header]
        return None


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    # Create the server, binding to localhost on port 8080
    server = socketserver.TCPServer((HOST, PORT), MyWebServer)

    # Activate the server; this will keep running until you
    # interrupt the program with Ctrl-C
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server interrupted, closing webserver ...")
        server.server_close()
