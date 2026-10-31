CREATE TABLE nx_api_key (
	id VARCHAR(32) NOT NULL,
	owner VARCHAR(32) NOT NULL,
	name VARCHAR(80) NOT NULL,
	prefix VARCHAR(16) NOT NULL,
	key_hash VARCHAR(64) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	last_used_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (key_hash)
);

CREATE INDEX ix_nx_api_key_owner ON nx_api_key (owner);

CREATE TABLE nx_knowledge_base (
	id VARCHAR(32) NOT NULL,
	name VARCHAR(120) NOT NULL,
	description TEXT,
	color VARCHAR(16) NOT NULL,
	is_default BOOLEAN NOT NULL,
	created_by VARCHAR(32) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE nx_webhook (
	id VARCHAR(32) NOT NULL,
	url VARCHAR(500) NOT NULL,
	events VARCHAR(300) NOT NULL,
	secret VARCHAR(80) NOT NULL,
	active BOOLEAN NOT NULL,
	created_by VARCHAR(32) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	last_status INTEGER,
	last_error TEXT,
	last_delivery_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id)
);

CREATE TABLE nx_bot (
	id VARCHAR(32) NOT NULL,
	name VARCHAR(80) NOT NULL,
	description VARCHAR(300),
	base_id VARCHAR(32) NOT NULL,
	instructions TEXT,
	greeting VARCHAR(500),
	fallback VARCHAR(500),
	color VARCHAR(16) NOT NULL,
	cite_sources BOOLEAN NOT NULL,
	created_by VARCHAR(32) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(base_id) REFERENCES nx_knowledge_base (id)
);

CREATE INDEX ix_nx_bot_base_id ON nx_bot (base_id);

CREATE TABLE nx_document (
	id VARCHAR(32) NOT NULL,
	base_id VARCHAR(32) NOT NULL,
	kind VARCHAR(10) NOT NULL,
	extension VARCHAR(10) NOT NULL,
	title VARCHAR(200) NOT NULL,
	filename VARCHAR(255) NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	content TEXT,
	size_bytes INTEGER NOT NULL,
	pages INTEGER NOT NULL,
	chunks INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	error TEXT,
	uploaded_by VARCHAR(32) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	indexed_at TIMESTAMP WITHOUT TIME ZONE,
	updated_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT uk_document_base_sha256 UNIQUE (base_id, sha256),
	FOREIGN KEY(base_id) REFERENCES nx_knowledge_base (id) ON DELETE CASCADE
);

CREATE INDEX ix_nx_document_base_id ON nx_document (base_id);

CREATE INDEX ix_nx_document_status ON nx_document (status);

CREATE INDEX ix_nx_document_uploaded_by ON nx_document (uploaded_by);

CREATE TABLE nx_conversation (
	id VARCHAR(32) NOT NULL,
	owner VARCHAR(32) NOT NULL,
	bot_id VARCHAR(32),
	title VARCHAR(160) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(bot_id) REFERENCES nx_bot (id) ON DELETE CASCADE
);

CREATE INDEX ix_nx_conversation_bot_id ON nx_conversation (bot_id);

CREATE INDEX ix_nx_conversation_owner ON nx_conversation (owner);

CREATE INDEX ix_nx_conversation_updated_at ON nx_conversation (updated_at);

CREATE TABLE nx_whatsapp_channel (
	id VARCHAR(32) NOT NULL,
	name VARCHAR(80) NOT NULL,
	provider VARCHAR(16) NOT NULL,
	bot_id VARCHAR(32),
	auto_reply BOOLEAN NOT NULL,
	active BOOLEAN NOT NULL,
	phone VARCHAR(32),
	verify_token VARCHAR(64) NOT NULL,
	webhook_token VARCHAR(64) NOT NULL,
	api_version VARCHAR(16),
	phone_number_id VARCHAR(64),
	access_token TEXT,
	app_secret VARCHAR(200),
	base_url VARCHAR(300),
	api_key VARCHAR(200),
	instance VARCHAR(80),
	created_by VARCHAR(32) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	last_event_at TIMESTAMP WITHOUT TIME ZONE,
	last_error TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY(bot_id) REFERENCES nx_bot (id) ON DELETE SET NULL
);

CREATE TABLE nx_conversation_document (
	conversation_id VARCHAR(32) NOT NULL,
	document_id VARCHAR(32) NOT NULL,
	PRIMARY KEY (conversation_id, document_id),
	FOREIGN KEY(conversation_id) REFERENCES nx_conversation (id) ON DELETE CASCADE,
	FOREIGN KEY(document_id) REFERENCES nx_document (id) ON DELETE CASCADE
);

CREATE TABLE nx_message (
	id VARCHAR(32) NOT NULL,
	conversation_id VARCHAR(32) NOT NULL,
	role VARCHAR(10) NOT NULL,
	content TEXT NOT NULL,
	grounded BOOLEAN,
	answered BOOLEAN,
	model VARCHAR(120),
	latency_ms INTEGER,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(conversation_id) REFERENCES nx_conversation (id) ON DELETE CASCADE
);

CREATE INDEX ix_nx_message_conversation_created ON nx_message (conversation_id, created_at);

CREATE INDEX ix_nx_message_conversation_id ON nx_message (conversation_id);

CREATE TABLE nx_whatsapp_contact (
	id VARCHAR(32) NOT NULL,
	channel_id VARCHAR(32) NOT NULL,
	phone VARCHAR(32) NOT NULL,
	name VARCHAR(120),
	bot_enabled BOOLEAN NOT NULL,
	needs_human BOOLEAN NOT NULL,
	unread INTEGER NOT NULL,
	last_message_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uk_whatsapp_contact_channel_phone UNIQUE (channel_id, phone),
	FOREIGN KEY(channel_id) REFERENCES nx_whatsapp_channel (id) ON DELETE CASCADE
);

CREATE INDEX ix_nx_whatsapp_contact_channel_id ON nx_whatsapp_contact (channel_id);

CREATE INDEX ix_nx_whatsapp_contact_last_message_at ON nx_whatsapp_contact (last_message_at);

CREATE TABLE nx_feedback (
	id SERIAL NOT NULL,
	message_id VARCHAR(32) NOT NULL,
	owner VARCHAR(32) NOT NULL,
	rating INTEGER NOT NULL,
	comment TEXT,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uk_feedback_message_owner UNIQUE (message_id, owner),
	FOREIGN KEY(message_id) REFERENCES nx_message (id) ON DELETE CASCADE
);

CREATE TABLE nx_message_source (
	id SERIAL NOT NULL,
	message_id VARCHAR(32) NOT NULL,
	document_id VARCHAR(32),
	document_title VARCHAR(200) NOT NULL,
	chunk_id VARCHAR(80) NOT NULL,
	page INTEGER NOT NULL,
	rank INTEGER NOT NULL,
	similarity FLOAT,
	rerank_score FLOAT,
	excerpt TEXT NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(message_id) REFERENCES nx_message (id) ON DELETE CASCADE,
	FOREIGN KEY(document_id) REFERENCES nx_document (id) ON DELETE SET NULL
);

CREATE INDEX ix_nx_message_source_document_id ON nx_message_source (document_id);

CREATE INDEX ix_nx_message_source_message_id ON nx_message_source (message_id);

CREATE TABLE nx_whatsapp_message (
	id VARCHAR(32) NOT NULL,
	contact_id VARCHAR(32) NOT NULL,
	direction VARCHAR(3) NOT NULL,
	author VARCHAR(40) NOT NULL,
	body TEXT NOT NULL,
	status VARCHAR(12) NOT NULL,
	external_id VARCHAR(128),
	error TEXT,
	answered BOOLEAN,
	sources_json TEXT,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(contact_id) REFERENCES nx_whatsapp_contact (id) ON DELETE CASCADE
);

CREATE INDEX ix_nx_whatsapp_message_contact_created ON nx_whatsapp_message (contact_id, created_at);

CREATE INDEX ix_nx_whatsapp_message_external_id ON nx_whatsapp_message (external_id);
