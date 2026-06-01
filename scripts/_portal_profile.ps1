$c = Get-Content factory-portal.html -Raw
$size = (Get-Item factory-portal.html).Length
Write-Host ("File: {0:N0} bytes ({1:N1} KB)" -f $size, ($size/1KB))
Write-Host ("Lines: " + ((Get-Content factory-portal.html | Measure-Object -Line).Lines))
Write-Host ("script tags: " + ([regex]::Matches($c, '<script').Count))
Write-Host ("style tags: " + ([regex]::Matches($c, '<style').Count))
Write-Host ("data:image URIs: " + ([regex]::Matches($c, 'data:image/').Count))
Write-Host ("base64 blocks: " + ([regex]::Matches($c, 'base64,').Count))
Write-Host ("external scripts: " + ([regex]::Matches($c, 'script[^>]*src=').Count))
Write-Host ("fetch calls: " + ([regex]::Matches($c, 'fetch\(').Count))
Write-Host ("setInterval: " + ([regex]::Matches($c, 'setInterval\(').Count))
Write-Host ("setTimeout: " + ([regex]::Matches($c, 'setTimeout\(').Count))
Write-Host ""
Write-Host "Top 5 base64 blobs:"
[regex]::Matches($c, 'base64,[A-Za-z0-9+/=]+') | Sort-Object { $_.Length } -Descending | Select-Object -First 5 | ForEach-Object { "  {0,6:N1} KB" -f ($_.Length/1KB) }
