# Provider connection checks

The first provider check supports an OpenAI API key saved in the encrypted local vault.

## How it works

- The owner must be signed in and explicitly press the connection-test action.
- The API accepts only a vault credential ID and the vault passphrase; the API key itself is read internally from the encrypted vault.
- Only records whose provider is `openai` and type is `api_key` are eligible.
- The check sends one HTTPS GET request to the fixed endpoint `https://api.openai.com/v1/models`.
- Redirects are disabled, the request timeout is eight seconds, and response bodies and authorization headers are never returned or logged.
- The endpoint returns a small status such as `connected`, `invalid_credential`, `insufficient_permissions`, `rate_limited`, or `provider_unreachable`.

This is an explicit outbound request to OpenAI. It is not run automatically on page load or during credential storage. A successful check confirms that the key can access the models endpoint at that moment; it does not confirm billing status, model availability, or that every API operation is permitted.

Keep the application on loopback and do not enter production credentials until the authentication, vault backup/restore, and independent security review are complete.
