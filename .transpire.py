from transpire.resources import ConfigMap, Deployment, Ingress, Secret, Service

name = "notes"


KEYCLOAK_PEM = "MIIClTCCAX0CBgFrWCaGbjANBgkqhkiG9w0BAQsFADAOMQwwCgYDVQQDDANPQ0YwHhcNMTkwNjE0MjIzOTA4WhcNMjkwNjE0MjI0MDQ4WjAOMQwwCgYDVQQDDANPQ0YwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCZic2k64Nljah1y1qVbWn87VWp9VyXSkX+FJPZJVK3QjtLRLppQZV107VJ6P7zh9GwSxWOZqT3K6S4dATPqZM1OCowGzurryfeB9fs4cYyNTC4z7JjAvs0P1RsMKyQkRVevF7k2QjVBfTTGg6y27lCCFUyfsknx7/qabFQsPxinfQKSDBus+Epf1WcRHKmvBYYARDkTt0hsQ4B2EL+9PUHrXh80Ss6DjvYpUuaaBRcR2pZEaN9Fa5aH9n6m8KxmLhguODgoFZwrpJcujkePD+oW7NMMx6wO0SzVyKEIpdBPeFprUMXlq5LwBbEcGWYT3yEfkYTFlEu8qvqPObrvohNAgMBAAEwDQYJKoZIhvcNAQELBQADggEBAG0NG14VMoGLPELaQv8Dqch9BKW/6pmX5FwQF/siVc9fK9hhKxDjpnDHLJD8/s2VcOiSQo66kF/Mo6Agp4LR/FglNjOXjQnM+9XXROFbHpPXbRPswxjgGQb00UTwAw2KB8X9gpiVEKNnPUjQyj6doKlKpPbFutTdCAjupu4bWhZJc5m/H2ui8ImYed5OPrEN1HfUIwPzndqPEsxLRnpPU/TPfTHIhvDXtMWgeQtXt5EZb71SGIYpJzxM9gPtH2DMtAo6GfaoX2tiuafmly4QQkWs7qfMeOcPjqCvj9bbwxiMfe2f0UsxYBPowvD8a8FXnJe0C8YXpkcvyOWzGsTbA/Y="


def objects():
    # Postgres database for notes
    yield {
        "apiVersion": "acid.zalan.do/v1",
        "kind": "postgresql",
        "metadata": {"name": "ocf-notes"},
        "spec": {
            "teamId": "ocf",
            "volume": {
                "size": "8Gi",
                "storageClass": "rbd-nvme",
            },
            "numberOfInstances": 1,
            "users": {"notes": ["superuser", "createdb"]},
            "databases": {"notes": "notes"},
            "postgresql": {"version": "15"},
        },
    }

    # Object storage bucket for uploads
    yield {
        "apiVersion": "objectbucket.io/v1alpha1",
        "kind": "ObjectBucketClaim",
        "metadata": {"name": "ocf-notes-bucket"},
        "spec": {
            "generateBucketName": "ocf-notes",
            "storageClassName": "rgw-hdd",
        },
    }

    cm = ConfigMap("keycloak-pem", data={"keycloak.pem": KEYCLOAK_PEM})
    yield cm.build()

    secret = Secret(
        "hedgedoc",
        string_data={
            "session-secret": "",
            "oidc-client-secret": "",
        },
    )
    yield secret.build()

    dep = Deployment(
        name="hedgedoc",
        image="quay.io/hedgedoc/hedgedoc:1.9.7-alpine",
        ports=[3000],
    )

    dep.obj.spec.template.spec.volumes = [
        {
            "name": "keycloak-pem",
            "configMap": {"name": cm.obj.metadata.name},
        },
    ]

    dep.obj.spec.template.spec.containers[0].volume_mounts = [
        {
            "name": "keycloak-pem",
            "mountPath": "/keycloak.pem",
            "subPath": "keycloak.pem",
        }
    ]

    env = {
        "CMD_DOMAIN": "notes.ocf.berkeley.edu",
        "CMD_PROTOCOL_USESSL": "true",
        "CMD_ALLOW_ANONYMOUS": "false",
        "CMD_ALLOW_ANONYMOUS_EDITS": "false",
        "CMD_EMAIL": "false",
        "CMD_ALLOW_EMAIL_REGISTER": "false",
        "CMD_OAUTH2_USER_PROFILE_URL": "https://idm.ocf.berkeley.edu/realms/ocf/protocol/openid-connect/userinfo",
        "CMD_OAUTH2_USER_PROFILE_USERNAME_ATTR": "preferred_username",
        "CMD_OAUTH2_USER_PROFILE_DISPLAY_NAME_ATTR": "name",
        "CMD_OAUTH2_USER_PROFILE_EMAIL_ATTR": "email",
        "CMD_OAUTH2_TOKEN_URL": "https://idm.ocf.berkeley.edu/realms/ocf/protocol/openid-connect/token",
        "CMD_OAUTH2_AUTHORIZATION_URL": "https://idm.ocf.berkeley.edu/realms/ocf/protocol/openid-connect/auth",
        "CMD_OAUTH2_CLIENT_ID": "hedgedoc",
        "CMD_OAUTH2_PROVIDERNAME": "OCF",
        "CMD_OAUTH2_SCOPE": "openid email profile",
        "CMD_DB_URL": "postgres://$(_DB_USER):$(_DB_PASS)@ocf-notes:5432/notes?ssl=no-verify",
        "CMD_DB_DIALECT": "postgres",
        "CMD_S3_ENDPOINT": "https://o3.ocf.io",
    }

    dep.obj.spec.template.spec.containers[0].env = [
        {
            "name": "_DB_USER",
            "valueFrom": {
                "secretKeyRef": {
                    "name": "notes.ocf-notes.credentials.postgresql.acid.zalan.do",
                    "key": "username",
                }
            },
        },
        {
            "name": "_DB_PASS",
            "valueFrom": {
                "secretKeyRef": {
                    "name": "notes.ocf-notes.credentials.postgresql.acid.zalan.do",
                    "key": "password",
                }
            },
        },
        {
            "name": "CMD_SESSION_SECRET",
            "valueFrom": {
                "secretKeyRef": {
                    "name": secret.obj.metadata.name,
                    "key": "session-secret",
                }
            },
        },
        {
            "name": "CMD_OAUTH2_CLIENT_SECRET",
            "valueFrom": {
                "secretKeyRef": {
                    "name": secret.obj.metadata.name,
                    "key": "oidc-client-secret",
                }
            },
        },
        {
            "name": "CMD_S3_BUCKET",
            "valueFrom": {
                "configMapKeyRef": {
                    "name": "ocf-notes-bucket",
                    "key": "BUCKET_NAME",
                }
            },
        },
        {
            "name": "CMD_S3_ACCESS_KEY_ID",
            "valueFrom": {
                "secretKeyRef": {
                    "name": "ocf-notes-bucket",
                    "key": "AWS_ACCESS_KEY_ID",
                }
            },
        },
        {
            "name": "CMD_S3_SECRET_ACCESS_KEY",
            "valueFrom": {
                "secretKeyRef": {
                    "name": "ocf-notes-bucket",
                    "key": "AWS_SECRET_ACCESS_KEY",
                }
            },
        },
        *[{"name": k, "value": v} for k, v in env.items()],
    ]

    yield dep.build()

    svc = Service(
        name="hedgedoc",
        selector=dep.get_selector(),
        port_on_pod=3000,
        port_on_svc=80,
    )

    yield svc.build()

    ing = Ingress.from_svc(
        svc=svc,
        host="notes.ocf.berkeley.edu",
        path_prefix="/",
    )

    yield ing.build()
