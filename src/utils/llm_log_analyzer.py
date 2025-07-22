"""
Utility for analyzing LLM logs and generating insights.
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter

from src.core.logging import get_logger

logger = get_logger(__name__)


class LLMLogAnalyzer:
    """Analyzer for LLM chain and debug logs."""
    
    def __init__(self, log_base_dir: str = "logs/llm"):
        self.log_base_dir = Path(log_base_dir)
        self.chain_log_dir = self.log_base_dir / "chains"
        self.debug_log_dir = self.log_base_dir / "debug"
        self.performance_log_dir = self.log_base_dir / "performance"
    
    def _load_jsonl_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load a JSON Lines file."""
        logs = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            logs.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse log line: {e}")
        except FileNotFoundError:
            logger.warning(f"Log file not found: {file_path}")
        except Exception as e:
            logger.error(f"Error loading log file {file_path}: {e}")
        
        return logs
    
    def load_logs_by_date(self, date: str, log_type: str = "chains") -> List[Dict[str, Any]]:
        """Load logs for a specific date."""
        if log_type == "chains":
            file_path = self.chain_log_dir / f"chains-{date}.jsonl"
        elif log_type == "debug":
            file_path = self.debug_log_dir / f"debug-{date}.jsonl"
        elif log_type == "performance":
            file_path = self.performance_log_dir / f"performance-{date}.jsonl"
        else:
            raise ValueError(f"Unknown log type: {log_type}")
        
        return self._load_jsonl_file(file_path)
    
    def load_logs_range(self, start_date: str, end_date: str, log_type: str = "chains") -> List[Dict[str, Any]]:
        """Load logs for a date range."""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        all_logs = []
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            logs = self.load_logs_by_date(date_str, log_type)
            all_logs.extend(logs)
            current += timedelta(days=1)
        
        return all_logs
    
    def analyze_provider_usage(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze provider usage patterns."""
        provider_stats = defaultdict(lambda: {
            "total_requests": 0,
            "total_duration": 0,
            "total_tokens": 0,
            "errors": 0,
            "models": Counter(),
            "task_types": Counter()
        })
        
        for log in logs:
            if log.get("log_type") in ["chain_step", "completion"] and log.get("provider"):
                provider = log["provider"]
                stats = provider_stats[provider]
                
                stats["total_requests"] += 1
                stats["total_duration"] += log.get("duration_ms", 0)
                
                if log.get("usage_stats", {}).get("total_tokens"):
                    stats["total_tokens"] += log["usage_stats"]["total_tokens"]
                
                if log.get("error_message"):
                    stats["errors"] += 1
                
                if log.get("model"):
                    stats["models"][log["model"]] += 1
                
                if log.get("task_type"):
                    stats["task_types"][log["task_type"]] += 1
        
        # Convert to regular dict and add averages
        result = {}
        for provider, stats in provider_stats.items():
            result[provider] = {
                "total_requests": stats["total_requests"],
                "total_duration_ms": stats["total_duration"],
                "avg_duration_ms": stats["total_duration"] / max(stats["total_requests"], 1),
                "total_tokens": stats["total_tokens"],
                "avg_tokens_per_request": stats["total_tokens"] / max(stats["total_requests"], 1),
                "error_rate": stats["errors"] / max(stats["total_requests"], 1),
                "top_models": dict(stats["models"].most_common(5)),
                "task_type_distribution": dict(stats["task_types"])
            }
        
        return result
    
    def analyze_task_performance(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance by task type."""
        task_stats = defaultdict(lambda: {
            "count": 0,
            "total_duration": 0,
            "durations": [],
            "providers": Counter(),
            "errors": 0
        })
        
        for log in logs:
            if log.get("task_type") and log.get("duration_ms") is not None:
                task_type = log["task_type"]
                duration = log["duration_ms"]
                
                stats = task_stats[task_type]
                stats["count"] += 1
                stats["total_duration"] += duration
                stats["durations"].append(duration)
                
                if log.get("provider"):
                    stats["providers"][log["provider"]] += 1
                
                if log.get("error_message"):
                    stats["errors"] += 1
        
        # Calculate statistics
        result = {}
        for task_type, stats in task_stats.items():
            durations = stats["durations"]
            result[task_type] = {
                "total_requests": stats["count"],
                "avg_duration_ms": stats["total_duration"] / max(stats["count"], 1),
                "min_duration_ms": min(durations) if durations else 0,
                "max_duration_ms": max(durations) if durations else 0,
                "p95_duration_ms": sorted(durations)[int(0.95 * len(durations))] if len(durations) > 20 else max(durations) if durations else 0,
                "error_rate": stats["errors"] / max(stats["count"], 1),
                "preferred_providers": dict(stats["providers"].most_common(3))
            }
        
        return result
    
    def analyze_error_patterns(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze error patterns and common failures."""
        error_patterns = {
            "by_provider": Counter(),
            "by_model": Counter(),
            "by_task_type": Counter(),
            "by_error_type": Counter(),
            "recent_errors": [],
            "error_timeline": []
        }
        
        for log in logs:
            if log.get("error_message"):
                error_msg = log["error_message"]
                timestamp = log.get("timestamp", "")
                
                # Count by various dimensions
                if log.get("provider"):
                    error_patterns["by_provider"][log["provider"]] += 1
                
                if log.get("model"):
                    error_patterns["by_model"][log["model"]] += 1
                
                if log.get("task_type"):
                    error_patterns["by_task_type"][log["task_type"]] += 1
                
                # Categorize error types
                error_type = "unknown"
                error_lower = error_msg.lower()
                if "timeout" in error_lower or "timed out" in error_lower:
                    error_type = "timeout"
                elif "rate limit" in error_lower or "429" in error_lower:
                    error_type = "rate_limit"
                elif "auth" in error_lower or "401" in error_lower:
                    error_type = "authentication"
                elif "quota" in error_lower or "exceeded" in error_lower:
                    error_type = "quota_exceeded"
                elif "404" in error_lower or "not found" in error_lower:
                    error_type = "not_found"
                elif "json" in error_lower or "parse" in error_lower:
                    error_type = "parsing"
                
                error_patterns["by_error_type"][error_type] += 1
                
                # Store recent errors for detailed analysis
                error_patterns["recent_errors"].append({
                    "timestamp": timestamp,
                    "provider": log.get("provider"),
                    "model": log.get("model"),
                    "task_type": log.get("task_type"),
                    "error_message": error_msg[:200],
                    "error_type": error_type
                })
                
                error_patterns["error_timeline"].append({
                    "timestamp": timestamp,
                    "error_type": error_type
                })
        
        # Sort recent errors by timestamp
        error_patterns["recent_errors"].sort(key=lambda x: x["timestamp"], reverse=True)
        error_patterns["recent_errors"] = error_patterns["recent_errors"][:20]  # Keep last 20
        
        # Convert counters to dicts
        error_patterns["by_provider"] = dict(error_patterns["by_provider"])
        error_patterns["by_model"] = dict(error_patterns["by_model"])
        error_patterns["by_task_type"] = dict(error_patterns["by_task_type"])
        error_patterns["by_error_type"] = dict(error_patterns["by_error_type"])
        
        return error_patterns
    
    def analyze_cost_efficiency(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze cost efficiency across providers and models."""
        # Rough cost estimates (tokens per dollar)
        cost_per_1k_tokens = {
            "groq": {
                "default": 0.0001,  # Very cheap
                "thinking": 0.0002
            },
            "gemini": {
                "flash": 0.0001,
                "pro": 0.002
            },
            "mistral": {
                "small": 0.0002,
                "large": 0.002
            }
        }
        
        cost_analysis = defaultdict(lambda: {
            "total_tokens": 0,
            "estimated_cost": 0,
            "requests": 0,
            "avg_cost_per_request": 0
        })
        
        for log in logs:
            if log.get("usage_stats", {}).get("total_tokens") and log.get("provider"):
                tokens = log["usage_stats"]["total_tokens"]
                provider = log["provider"]
                model = log.get("model", "default")
                
                # Estimate cost
                provider_costs = cost_per_1k_tokens.get(provider, {})
                rate = provider_costs.get(model, provider_costs.get("default", 0.001))
                estimated_cost = (tokens / 1000) * rate
                
                key = f"{provider}:{model}"
                stats = cost_analysis[key]
                stats["total_tokens"] += tokens
                stats["estimated_cost"] += estimated_cost
                stats["requests"] += 1
        
        # Calculate averages
        for key, stats in cost_analysis.items():
            if stats["requests"] > 0:
                stats["avg_cost_per_request"] = stats["estimated_cost"] / stats["requests"]
                stats["avg_tokens_per_request"] = stats["total_tokens"] / stats["requests"]
        
        return dict(cost_analysis)
    
    def generate_summary_report(self, date: str) -> Dict[str, Any]:
        """Generate a comprehensive summary report for a date."""
        chain_logs = self.load_logs_by_date(date, "chains")
        debug_logs = self.load_logs_by_date(date, "debug")
        performance_logs = self.load_logs_by_date(date, "performance")
        
        all_logs = chain_logs + debug_logs + performance_logs
        
        report = {
            "date": date,
            "summary": {
                "total_chain_logs": len(chain_logs),
                "total_debug_logs": len(debug_logs),
                "total_performance_logs": len(performance_logs),
                "total_logs": len(all_logs)
            },
            "provider_usage": self.analyze_provider_usage(chain_logs),
            "task_performance": self.analyze_task_performance(chain_logs),
            "error_analysis": self.analyze_error_patterns(all_logs),
            "cost_efficiency": self.analyze_cost_efficiency(chain_logs)
        }
        
        return report
    
    def export_to_csv(self, logs: List[Dict[str, Any]], output_file: str):
        """Export logs to CSV for external analysis."""
        if not logs:
            logger.warning("No logs to export")
            return
        
        try:
            # Flatten nested dictionaries
            flattened_logs = []
            for log in logs:
                flat_log = {}
                for key, value in log.items():
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            flat_log[f"{key}_{sub_key}"] = sub_value
                    elif isinstance(value, list):
                        flat_log[key] = str(value)  # Convert list to string
                    else:
                        flat_log[key] = value
                flattened_logs.append(flat_log)
            
            # Create DataFrame and export
            df = pd.DataFrame(flattened_logs)
            df.to_csv(output_file, index=False)
            logger.info(f"Exported {len(logs)} logs to {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to export logs to CSV: {e}")


def main():
    """CLI interface for log analysis."""
    import sys
    from datetime import datetime
    
    analyzer = LLMLogAnalyzer()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m src.utils.llm_log_analyzer report [date]")
        print("  python -m src.utils.llm_log_analyzer export [date] [output.csv]")
        return
    
    command = sys.argv[1]
    
    if command == "report":
        date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")
        report = analyzer.generate_summary_report(date)
        
        print(f"\n=== LLM Log Analysis Report for {date} ===")
        print(f"Total logs: {report['summary']['total_logs']}")
        print(f"Chain logs: {report['summary']['total_chain_logs']}")
        print(f"Debug logs: {report['summary']['total_debug_logs']}")
        print(f"Performance logs: {report['summary']['total_performance_logs']}")
        
        print("\n--- Provider Usage ---")
        for provider, stats in report['provider_usage'].items():
            print(f"{provider}: {stats['total_requests']} requests, "
                  f"avg {stats['avg_duration_ms']:.0f}ms, "
                  f"error rate {stats['error_rate']:.2%}")
        
        print("\n--- Task Performance ---")
        for task, stats in report['task_performance'].items():
            print(f"{task}: {stats['total_requests']} requests, "
                  f"avg {stats['avg_duration_ms']:.0f}ms, "
                  f"p95 {stats['p95_duration_ms']:.0f}ms")
        
        print("\n--- Recent Errors ---")
        for error in report['error_analysis']['recent_errors'][:5]:
            print(f"  {error['timestamp']}: {error['provider']} - {error['error_message'][:100]}")
    
    elif command == "export":
        date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")
        output_file = sys.argv[3] if len(sys.argv) > 3 else f"llm_logs_{date}.csv"
        
        logs = analyzer.load_logs_by_date(date, "chains")
        analyzer.export_to_csv(logs, output_file)
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()