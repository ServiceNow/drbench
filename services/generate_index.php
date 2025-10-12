#!/usr/bin/env php
<?php
/**
 * Generate index.php with actual Docker port mappings
 * Usage: php generate_index.php '{"nextcloud": 55024, "mattermost": 55025, ...}'
 */

if ($argc < 2) {
    fwrite(STDERR, "Usage: php generate_index.php '<port_mappings_json>'\n");
    exit(1);
}

$port_mappings_json = $argv[1];
$port_mappings = json_decode($port_mappings_json, true);

if (json_last_error() !== JSON_ERROR_NONE) {
    fwrite(STDERR, "Error: Invalid JSON provided\n");
    exit(1);
}

// Extract port mappings for services
$service_ports = [];
foreach ($port_mappings as $app_name => $app_info) {
    $service_ports[$app_name] = $app_info['host_port'] ?? $app_info;
}

// Generate the HTML with embedded port URLs
$html = <<<HTML
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
HTML;

// Service definitions with their expected port mappings
$services = [
    'nextcloud' => [
        'label' => 'Nextcloud',
        'image' => '/images/nextcloud.svg',
        'alt' => 'Nextcloud'
    ],
    'mattermost' => [
        'label' => 'Mattermost', 
        'image' => '/images/mattermost.svg',
        'alt' => 'Mattermost'
    ],
    'filebrowser' => [
        'label' => 'File Browser',
        'image' => '/images/filebrowser.svg', 
        'alt' => 'File Browser'
    ],
    'novnc' => [
        'label' => 'VNC Desktop',
        'image' => 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNTYgMjU2IiB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiI+CiAgICA8ZyBmaWxsPSJub25lIiBzdHJva2U9Im5vbmUiIHN0cm9rZS13aWR0aD0iMSIgZmlsbC1ydWxlPSJldmVub2RkIj4KICAgICAgICA8cmVjdCBmaWxsPSIjMzQ0OTVFIiB4PSIzMiIgeT0iMzIiIHdpZHRoPSIxOTIiIGhlaWdodD0iMTkyIiByeD0iMTYiLz4KICAgICAgICA8cmVjdCBmaWxsPSIjMjEyRjNDIiB4PSI0OCIgeT0iNDgiIHdpZHRoPSIxNjAiIGhlaWdodD0iMTIwIiByeD0iOCIvPgogICAgICAgIDxjaXJjbGUgZmlsbD0iIzFBQkM5QyIgY3g9IjE2MCIgY3k9IjE5MiIgcj0iMTYiLz4KICAgICAgICA8Y2lyY2xlIGZpbGw9IiNFNzRDM0MiIGN4PSI5NiIgY3k9IjE5MiIgcj0iMTYiLz4KICAgICAgICA8Y2lyY2xlIGZpbGw9IiMzNDk4REIiIGN4PSIxMjgiIGN5PSIxOTIiIHI9IjE2Ii8+CiAgICAgICAgPHBhdGggZD0iTTg4LDgwIEwxNjgsODAgTDE2OCwxMzYgTDg4LDEzNiBMODgsODAiIGZpbGw9IiNFQ0YwRjEiLz4KICAgIDwvZz4KPC9zdmc+',
        'alt' => 'noVNC'
    ],
    'email' => [
        'label' => 'Email',
        'image' => 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiIgdmlld0JveD0iMCAwIDI1NiAyNTYiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIyNTYiIGhlaWdodD0iMjU2IiByeD0iNjAiIGZpbGw9IiM0Mjg1RjQiLz4KPHBhdGggZD0iTTU2IDgwQzU2IDcxLjE2MzQgNjMuMTYzNCA2NCA3MiA2NEgxODRDMTkyLjgzNyA2NCAyMDAgNzEuMTYzNCAyMDAgODBWMTc2QzIwMCAxODQuODM3IDE5Mi44MzcgMTkyIDE4NCAxOTJINzJDNjMuMTYzNCAxOTIgNTYgMTg0LjgzNyA1NiAxNzZWODBaIiBmaWxsPSJ3aGl0ZSIvPgo8cGF0aCBkPSJNNzIgODBMMTI4IDEyMEwxODQgODAiIHN0cm9rZT0iIzQyODVGNCIgc3Ryb2tlLXdpZHRoPSI4IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+',
        'alt' => 'Email'
    ]
];

foreach ($services as $service_key => $service) {
    $port = $service_ports[$service_key] ?? null;
    
    if ($port) {
        $url = "http://localhost:{$port}/";
        $html .= sprintf(
            '        <a href="%s" class="tile">
            <img src="%s" alt="%s">
            <span class="tile-label">%s</span>
        </a>' . "\n",
            htmlspecialchars($url),
            htmlspecialchars($service['image']),
            htmlspecialchars($service['alt']),
            htmlspecialchars($service['label'])
        );
    }
}

$html .= <<<HTML
    </div>
</body>
</html>
HTML;

echo $html;
?>