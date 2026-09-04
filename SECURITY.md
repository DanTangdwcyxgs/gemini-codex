# Security

Never commit API keys, OAuth credentials, private IP addresses, local machine usernames, or personal filesystem paths.

Use environment variables or a local key file that is ignored by Git. Examples in this repository use placeholders and `localhost` only.

Before publishing changes, check for accidental secrets with a local secret scanner and inspect the final Git diff.
