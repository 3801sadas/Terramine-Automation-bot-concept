$dirs = Get-ChildItem 'C:\Users\Usernom\Downloads\TerraMine_+Real+World+Mining_1.1.45_APKPure' -Directory -Filter 'smali_classes*'
foreach ($d in $dirs) {
  $comPath = Join-Path $d.FullName 'com'
  if (Test-Path $comPath) {
    Write-Output "=== $($d.Name) ==="
    Get-ChildItem $comPath | ForEach-Object { Write-Output $_.Name }
    Write-Output ""
  }
}
