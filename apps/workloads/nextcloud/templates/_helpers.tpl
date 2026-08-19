{{- define "nextcloud.labels" -}}
app.kubernetes.io/part-of: nextcloud
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end }}
