{{- define "keycloak.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{/* ---------------------------------------------------------------------------------------
     keycloak.reuseOrGenerate -- a bootstrap credential: the admin user's password, or the admin
     service account's client secret. Called as (list $lookedUpSecret "<data key>" $explicit).

     Precedence:
       1. an explicit, non-empty value                              -> used as given
       2. the Secret already in the cluster carries <data key>      -> REUSED, byte for byte
       3. otherwise                                                 -> generated (32 alphanumerics)

     TAKES THE LOOKED-UP SECRET AS A PARAMETER AND NEVER CALLS `lookup` ITSELF. `helm template`
     disables lookup, so a decision sitting inline next to its own lookup could only ever render
     its generate arm, and the reuse arm, the one that runs on every upgrade of a live install,
     would be the untested one. hack/check-bootstrap-password.py hands this helper a found Secret
     and nothing at all, for every data key the chart uses, and asserts each arm (pattern:
     krateo-platformops/installer#782).

     WHY REUSE MATTERS. The operator applies spec.bootstrapAdmin only on the server's FIRST start;
     afterwards the credential lives in Keycloak's database. A regenerated Secret would not change
     the live credential, it would make the Secret lie about it, and the next reader would be
     locked out with nothing saying why.
     --------------------------------------------------------------------------------------- */}}
{{- define "keycloak.reuseOrGenerate" -}}
{{- $found := index . 0 -}}
{{- $key := index . 1 -}}
{{- $explicit := index . 2 -}}
{{- if $explicit -}}
{{- $explicit -}}
{{- else if and $found $found.data (hasKey $found.data $key) -}}
{{- index $found.data $key | b64dec -}}
{{- else -}}
{{- randAlphaNum 32 -}}
{{- end -}}
{{- end -}}
