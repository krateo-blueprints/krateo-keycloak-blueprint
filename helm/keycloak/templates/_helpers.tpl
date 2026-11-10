{{- define "keycloak.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{/* ---------------------------------------------------------------------------------------
     keycloak.bootstrapAdminPassword — the bootstrap admin's password.

     Precedence:
       1. an explicit, non-empty bootstrapAdmin.secret.password   -> used as given
       2. the Secret already in the cluster carries `password`    -> REUSED, byte for byte
       3. otherwise                                                -> generated (32 alphanumerics)

     TAKES THE LOOKED-UP SECRET AS A PARAMETER AND NEVER CALLS `lookup` ITSELF. `helm template`
     disables lookup, so a decision sitting inline next to its own lookup could only ever render
     its generate arm, and the reuse arm, the one that runs on every upgrade of a live install,
     would be the untested one. hack/check-bootstrap-password.py hands this helper a found Secret
     and nothing at all and asserts each arm (pattern: krateo-platformops/installer#782).

     WHY REUSE MATTERS. The operator applies spec.bootstrapAdmin only on the server's FIRST start;
     afterwards the password lives in Keycloak's database. A regenerated Secret would not change
     the live password, it would make the Secret lie about it, and the next person to read it
     would be locked out with nothing saying why.
     --------------------------------------------------------------------------------------- */}}
{{- define "keycloak.bootstrapAdminPassword" -}}
{{- $found := index . 0 -}}
{{- $explicit := index . 1 -}}
{{- if $explicit -}}
{{- $explicit -}}
{{- else if and $found $found.data (hasKey $found.data "password") -}}
{{- index $found.data "password" | b64dec -}}
{{- else -}}
{{- randAlphaNum 32 -}}
{{- end -}}
{{- end -}}
