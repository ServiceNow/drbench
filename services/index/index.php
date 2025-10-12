<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to DrBench</title>
    <style>
        body {
            font-family: sans-serif;
            margin: 0;
            padding: 40px;
            background-color: #f4f4f4;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .container {
            display: flex;
            flex-wrap: wrap;
            gap: 40px;
            justify-content: center;
            max-width: 1200px;
        }
        .tile {
            background-color: #fff;
            border: 1px solid #ddd;
            border-radius: 12px;
            width: 180px;
            height: 180px;
            padding: 20px;
            text-align: center;
            text-decoration: none;
            color: #333;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            transition: all 0.3s ease;
            box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        }
        .tile:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.1);
        }
        .tile img {
            max-width: 80%;
            max-height: 80%;
            height: auto;
            width: auto;
            object-fit: contain;
            margin-bottom: 15px;
        }
        .tile-label {
            font-size: 16px;
            font-weight: bold;
            margin-top: auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="#" onclick="openService('nextcloud')" class="tile">
            <img src="/images/nextcloud.svg" alt="Nextcloud">
            <span class="tile-label">Nextcloud</span>
        </a>
        <a href="#" onclick="openService('mattermost')" class="tile">
            <img src="/images/mattermost.svg" alt="Mattermost">
            <span class="tile-label">Mattermost</span>
        </a>
        <a href="#" onclick="openService('filebrowser')" class="tile">
            <img src="/images/filebrowser.svg" alt="File Browser">
            <span class="tile-label">File Browser</span>
        </a>
        <a href="#" onclick="openService('novnc')" class="tile">
            <img src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNTYgMjU2IiB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiI+CiAgICA8ZyBmaWxsPSJub25lIiBzdHJva2U9Im5vbmUiIHN0cm9rZS13aWR0aD0iMSIgZmlsbC1ydWxlPSJldmVub2RkIj4KICAgICAgICA8cmVjdCBmaWxsPSIjMzQ0OTVFIiB4PSIzMiIgeT0iMzIiIHdpZHRoPSIxOTIiIGhlaWdodD0iMTkyIiByeD0iMTYiLz4KICAgICAgICA8cmVjdCBmaWxsPSIjMjEyRjNDIiB4PSI0OCIgeT0iNDgiIHdpZHRoPSIxNjAiIGhlaWdodD0iMTIwIiByeD0iOCIvPgogICAgICAgIDxjaXJjbGUgZmlsbD0iIzFBQkM5QyIgY3g9IjE2MCIgY3k9IjE5MiIgcj0iMTYiLz4KICAgICAgICA8Y2lyY2xlIGZpbGw9IiNFNzRDM0MiIGN4PSI5NiIgY3k9IjE5MiIgcj0iMTYiLz4KICAgICAgICA8Y2lyY2xlIGZpbGw9IiMzNDk4REIiIGN4PSIxMjgiIGN5PSIxOTIiIHI9IjE2Ii8+CiAgICAgICAgPHBhdGggZD0iTTg4LDgwIEwxNjgsODAgTDE2OCwxMzYgTDg4LDEzNiBMODgsODAiIGZpbGw9IiNFQ0YwRjEiLz4KICAgIDwvZz4KPC9zdmc+" alt="noVNC">
            <span class="tile-label">VNC Desktop</span>
        </a>
        <a href="#" onclick="openService('mail')" class="tile">
            <img src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiIgdmlld0JveD0iMCAwIDI1NiAyNTYiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIyNTYiIGhlaWdodD0iMjU2IiByeD0iNjAiIGZpbGw9IiM0Mjg1RjQiLz4KPHBhdGggZD0iTTU2IDgwQzU2IDcxLjE2MzQgNjMuMTYzNCA2NCA3MiA2NEgxODRDMTkyLjgzNyA2NCAyMDAgNzEuMTYzNCAyMDAgODBWMTc2QzIwMCAxODQuODM3IDE5Mi44MzcgMTkyIDE4NCAxOTJINzJDNjMuMTYzNCAxOTIgNTYgMTg0LjgzNyA1NiAxNzZWODBaIiBmaWxsPSJ3aGl0ZSIvPgo8cGF0aCBkPSJNNzIgODBMMTI4IDEyMEwxODQgODAiIHN0cm9rZT0iIzQyODVGNCIgc3Ryb2tlLXdpZHRoPSI4IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+" alt="Email">
            <span class="tile-label">Email</span>
        </a>
    </div>

    <script>
        function openService(serviceName) {
            const currentHost = window.location.hostname;
            const currentPort = parseInt(window.location.port);
            
            // DrBench port mapping: each service gets consecutive external ports
            // Based on container port mappings:
            // 55010->1143, 55011->5901, 55012->6080, 55013->8080, 55014->8081, 55015->8082, 55016->8085, 55017->8090, 55018->8099, 55019->9090
            
            const servicePortMapping = {
                'nextcloud': currentPort + 1,   // 8081 -> next port after 8080
                'mattermost': currentPort + 2,  // 8082 -> two ports after 8080
                'novnc': currentPort - 1,       // 6080 -> one port before 8080
                'mail': currentPort + 3,        // 8085 -> three ports after 8080
                'filebrowser': currentPort + 4  // 8090 -> four ports after 8080
            };
            
            const serviceExternalPort = servicePortMapping[serviceName];
            const serviceUrl = `${window.location.protocol}//${currentHost}:${serviceExternalPort}/`;
            
            // Open service in same window
            window.location.href = serviceUrl;
        }
    </script>
</body>
</html>