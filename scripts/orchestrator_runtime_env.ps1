Set-StrictMode -Version Latest

function Import-PalWakfOpenAIRuntimeKey {
    $processValue = [Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "Process")
    if (-not [string]::IsNullOrWhiteSpace($processValue)) {
        if ([string]::IsNullOrWhiteSpace($env:PALWAKF_OPENAI_API_KEY_SOURCE)) {
            $env:PALWAKF_OPENAI_API_KEY_SOURCE = "process"
        }
        return
    }

    foreach ($scope in @("User", "Machine")) {
        $value = [Environment]::GetEnvironmentVariable("OPENAI_API_KEY", $scope)
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            [Environment]::SetEnvironmentVariable("OPENAI_API_KEY", $value, "Process")
            $env:PALWAKF_OPENAI_API_KEY_SOURCE = "windows_$($scope.ToLower())_inherited"
            return
        }
    }
}
