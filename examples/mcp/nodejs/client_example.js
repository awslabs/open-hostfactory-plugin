#!/usr/bin/env node
/**
 * Example Node.js MCP client for Open Resource Broker.
 *
 * Connects to the broker's catalog-driven MCP server over stdio and performs a
 * few common operations. The server is started as a subprocess with
 * `orb mcp serve` (stdio is the default transport), and every tool the server
 * exposes is derived from the broker's operation catalog.
 *
 * Install dependencies:
 *   npm install @modelcontextprotocol/sdk
 */

const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = require('@modelcontextprotocol/sdk/client/stdio.js');

class OpenResourceBrokerMCPClient {
  constructor() {
    // stdio is the default transport, so no extra flags are needed.
    // `orb mcp serve --transport http` would serve over Streamable HTTP.
    this.transport = new StdioClientTransport({
      command: 'orb',
      args: ['mcp', 'serve'],
    });

    this.client = new Client(
      { name: 'orb-nodejs-client', version: '1.0.0' },
      { capabilities: {} },
    );
  }

  async connect() {
    console.log('Connecting to MCP server...');
    await this.client.connect(this.transport);
    console.log('Connected successfully');
  }

  async disconnect() {
    await this.client.close();
    console.log('Disconnected');
  }

  async listTools() {
    const result = await this.client.listTools();
    console.log(`Found ${result.tools.length} tools:`, result.tools.map((t) => t.name));
    return result.tools;
  }

  async callTool(name, args = {}) {
    console.log(`Calling tool: ${name} with arguments:`, args);
    const result = await this.client.callTool({ name, arguments: args });
    // The catalog server renders each tool result as a single text block whose
    // text is the operation's canonical JSON body.
    const textBlock = (result.content || []).find((b) => b.type === 'text');
    const body = textBlock ? JSON.parse(textBlock.text) : null;
    console.log(`Tool ${name} isError=${result.isError} body=`, body);
    return body;
  }
}

async function exampleBasicOperations() {
  console.log('=== Basic MCP Operations Example ===');
  const client = new OpenResourceBrokerMCPClient();
  try {
    await client.connect();
    await client.listTools();
  } catch (error) {
    console.error('Error in basic operations:', error);
  } finally {
    await client.disconnect();
  }
}

async function exampleInfrastructureWorkflow() {
  console.log('=== Infrastructure Workflow Example ===');
  const client = new OpenResourceBrokerMCPClient();
  try {
    await client.connect();

    await client.callTool('list_providers');
    await client.callTool('get_provider_health');
    await client.callTool('list_templates', { active_only: true });

    // Requesting machines would provision real resources, so it is left
    // commented out. The catalog input field is `requested_count`.
    // await client.callTool('request_machines', {
    //   template_id: 'RunInstances-OnDemand',
    //   requested_count: 2,
    // });
  } catch (error) {
    console.error('Error in infrastructure workflow:', error);
  } finally {
    await client.disconnect();
  }
}

async function exampleErrorHandling() {
  console.log('=== Error Handling Example ===');
  const client = new OpenResourceBrokerMCPClient();
  try {
    await client.connect();
    const result = await client.client.callTool({ name: 'non_existent_tool', arguments: {} });
    console.log('Unknown tool isError=', result.isError);
  } catch (error) {
    console.error('Error in error handling example:', error);
  } finally {
    await client.disconnect();
  }
}

async function main() {
  console.log('Open Resource Broker MCP Client Examples');
  console.log('========================================');

  const examples = [
    exampleBasicOperations,
    exampleInfrastructureWorkflow,
    exampleErrorHandling,
  ];

  for (const example of examples) {
    try {
      await example();
      console.log();
    } catch (error) {
      console.error(`Error in ${example.name}:`, error);
      console.log();
    }
  }

  console.log('All examples completed');
}

if (require.main === module) {
  main().catch(console.error);
}

module.exports = { OpenResourceBrokerMCPClient };
