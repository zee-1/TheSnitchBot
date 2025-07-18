# Cloudflare CDN Integration - The Snitch Discord Bot

## Overview
Cloudflare CDN serves as the edge layer for The Snitch Discord bot, providing security, performance, and global distribution capabilities while leveraging the free tier for cost optimization.

## Architecture Integration

```
Discord API → Cloudflare CDN → Azure API Management → Azure Functions
             ↓
         Static Assets
         (Bot Images, Templates)
```

## Use Cases

### 1. Discord Webhook Endpoint Protection
**Purpose**: Secure and optimize Discord webhook delivery

**Implementation**:
- **Domain**: `bot.your-domain.com/discord/webhook`
- **Cloudflare Rules**:
  - Rate limiting: 100 requests/minute per IP
  - DDoS protection: Automatic
  - SSL: Full (strict)
  - Bot fight mode: Enabled

**Benefits**:
- Protects Azure Functions from malicious requests
- Handles Discord's webhook retry logic efficiently
- Global edge locations reduce latency

### 2. Static Asset Delivery
**Assets Cached**:
- Bot avatar and profile images
- Newsletter HTML templates
- Custom emoji and reaction images
- Help documentation and command guides
- Server analytics charts/graphs

**Cache Configuration**:
```
/static/images/*     - Cache for 30 days
/templates/*         - Cache for 1 day
/docs/*             - Cache for 1 hour
/api/health         - No cache
```

### 3. Newsletter Content Distribution
**Use Case**: Serve newsletter archives and rich content

**Implementation**:
- **Newsletter Archive**: `bot.your-domain.com/newsletters/{server_id}/{date}`
- **Rich Media**: Images, charts, embedded content in newsletters
- **RSS Feeds**: Optional RSS feeds for newsletter subscriptions

### 4. Bot API Documentation
**Purpose**: Host public API documentation and bot guides

**Content**:
- Command documentation
- Setup guides for server admins
- Privacy policy and terms of service
- Status page for bot uptime

## Technical Implementation

### 1. Cloudflare Configuration Module

```python
# src/services/cloudflare_service.py
class CloudflareService:
    def __init__(self, api_token: str, zone_id: str):
        self.api_token = api_token
        self.zone_id = zone_id
    
    async def purge_cache(self, urls: List[str]) -> bool:
        """Purge specific URLs from Cloudflare cache"""
        
    async def create_page_rule(self, pattern: str, settings: Dict) -> bool:
        """Create caching rules for specific URL patterns"""
        
    async def upload_to_r2(self, file_path: str, content: bytes) -> str:
        """Upload files to Cloudflare R2 storage"""
```

### 2. Azure Functions with Cloudflare Headers

```python
# Validate requests are coming through Cloudflare
@app.route(route="discord/webhook")
def discord_webhook(req: func.HttpRequest) -> func.HttpResponse:
    # Verify Cloudflare headers
    cf_connecting_ip = req.headers.get('CF-Connecting-IP')
    cf_ray = req.headers.get('CF-Ray')
    
    if not cf_connecting_ip:
        return func.HttpResponse("Forbidden", status_code=403)
    
    # Process Discord webhook
    return process_discord_webhook(req)
```

### 3. CDN-Optimized Asset Management

```python
# src/services/asset_service.py
class AssetService:
    def __init__(self, cloudflare_service: CloudflareService):
        self.cf = cloudflare_service
        self.cdn_base_url = "https://bot.your-domain.com"
    
    async def upload_newsletter_asset(self, server_id: str, content: bytes) -> str:
        """Upload newsletter images/assets to CDN"""
        file_path = f"newsletters/{server_id}/{uuid4()}.png"
        await self.cf.upload_to_r2(file_path, content)
        return f"{self.cdn_base_url}/{file_path}"
    
    async def get_cached_avatar(self, user_id: str) -> str:
        """Get cached user avatar URL"""
        return f"{self.cdn_base_url}/avatars/{user_id}.png"
```

## Cloudflare Workers (Optional Enhancement)

### Edge Computing for Bot Logic
```javascript
// Cloudflare Worker for simple bot responses
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // Handle simple commands at the edge
    if (url.pathname === '/api/ping') {
      return new Response('🤖 The Snitch is online!', {
        headers: { 'content-type': 'text/plain' }
      });
    }
    
    // Route complex requests to Azure
    return fetch(request);
  }
}
```

## Configuration

### 1. DNS Settings
```
CNAME bot.your-domain.com → your-azure-function-app.azurewebsites.net
```

### 2. Page Rules
```
bot.your-domain.com/static/*
- Cache Level: Cache Everything
- Edge Cache TTL: 1 month
- Browser Cache TTL: 1 day

bot.your-domain.com/api/*
- Cache Level: Bypass
- Disable Apps
- Disable Performance
```

### 3. Security Settings
```
Security Level: High
Bot Fight Mode: On
Rate Limiting: 100 req/min per IP
SSL: Full (Strict)
Always Use HTTPS: On
```

## Cost Optimization

### Free Tier Usage
- **Bandwidth**: 100GB/month free
- **Requests**: Unlimited on free plan
- **Page Rules**: 3 free rules
- **DDoS Protection**: Free and automatic
- **SSL**: Free and automatic

### Paid Features (if needed)
- **Cloudflare R2**: $0.015/GB storage
- **Workers**: $5/month for 10M requests
- **Advanced Rate Limiting**: $5/month

## Benefits for The Snitch Bot

### 1. **Performance**
- **Global Edge**: Reduced latency for Discord webhooks
- **Static Asset Caching**: Faster image/template delivery
- **Bandwidth Savings**: Reduced Azure egress costs

### 2. **Security**
- **DDoS Protection**: Automatic attack mitigation
- **Rate Limiting**: Prevent API abuse
- **SSL/TLS**: Secure webhook endpoints

### 3. **Reliability**
- **High Availability**: Cloudflare's 99.99% uptime
- **Failover**: Automatic routing around issues
- **Bot Protection**: Filter malicious traffic

### 4. **Analytics**
- **Traffic Insights**: Monitor bot usage patterns
- **Performance Metrics**: Track response times
- **Security Events**: Monitor attack attempts

## Implementation Priority

### Phase 1 (Immediate)
- Set up domain and basic CDN
- Configure Discord webhook endpoint
- Implement DDoS protection

### Phase 2 (Enhancement)
- Static asset caching
- Newsletter archive hosting
- Documentation site

### Phase 3 (Advanced)
- Cloudflare Workers for edge logic
- R2 storage for large assets
- Advanced analytics integration

This Cloudflare integration provides a robust, cost-effective edge layer that enhances The Snitch bot's performance, security, and global reach while staying within free tier limits.