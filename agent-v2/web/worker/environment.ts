export interface Environment {
	AGENT_DURABLE_OBJECT: DurableObjectNamespace
	OPENAI_API_KEY?: string
	ANTHROPIC_API_KEY?: string
	GOOGLE_API_KEY?: string
	/** Amazon Bedrock (SigV4). Same idea as app BEDROCK_MODEL_ID + AWS_REGION. */
	AWS_ACCESS_KEY_ID?: string
	AWS_SECRET_ACCESS_KEY?: string
	AWS_REGION?: string
	AWS_SESSION_TOKEN?: string
}
