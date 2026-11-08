#!/usr/bin/env -S uv run

"""
AWS Route 53 DNS Management CLI

Install dependencies:
    uv pip install typer rich boto3
"""

import sys
from typing import Optional, List, Dict, Any

import boto3
import typer
from botocore.exceptions import ClientError, BotoCoreError
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage AWS Route 53 DNS records")
console = Console()


class Route53Manager:
    """Manages Route 53 operations with dependency injection for testing."""
    
    def __init__(self, client=None):
        """Initialize with optional boto3 client for testing."""
        self.client = client or boto3.client('route53')
    
    def list_hosted_zones(self) -> List[Dict[str, Any]]:
        """Retrieve all hosted zones."""
        try:
            zones = []
            paginator = self.client.get_paginator('list_hosted_zones')
            for page in paginator.paginate():
                zones.extend(page['HostedZones'])
            return zones
        except (ClientError, BotoCoreError) as e:
            console.print(f"[red]Error listing zones: {e}[/red]")
            raise
    
    def list_resource_records(self, zone_id: str) -> List[Dict[str, Any]]:
        """Retrieve all resource record sets for a zone."""
        try:
            records = []
            paginator = self.client.get_paginator('list_resource_record_sets')
            for page in paginator.paginate(HostedZoneId=zone_id):
                records.extend(page['ResourceRecordSets'])
            return records
        except (ClientError, BotoCoreError) as e:
            console.print(f"[red]Error listing records: {e}[/red]")
            raise
    
    def add_record(
        self,
        zone_id: str,
        name: str,
        record_type: str,
        value: str,
        ttl: int = 300
    ) -> Dict[str, Any]:
        """Add a DNS record to a hosted zone."""
        try:
            # Ensure name ends with a dot for FQDN
            if not name.endswith('.'):
                name += '.'
            
            change_batch = {
                'Changes': [{
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': name,
                        'Type': record_type,
                        'TTL': ttl,
                        'ResourceRecords': [{'Value': value}]
                    }
                }]
            }
            
            response = self.client.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch=change_batch
            )
            return response
        except (ClientError, BotoCoreError) as e:
            console.print(f"[red]Error adding record: {e}[/red]")
            raise
    
    def delete_record(
        self,
        zone_id: str,
        name: str,
        record_type: str,
        value: str,
        ttl: int = 300
    ) -> Dict[str, Any]:
        """Delete a DNS record from a hosted zone."""
        try:
            # Ensure name ends with a dot for FQDN
            if not name.endswith('.'):
                name += '.'
            
            change_batch = {
                'Changes': [{
                    'Action': 'DELETE',
                    'ResourceRecordSet': {
                        'Name': name,
                        'Type': record_type,
                        'TTL': ttl,
                        'ResourceRecords': [{'Value': value}]
                    }
                }]
            }
            
            response = self.client.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch=change_batch
            )
            return response
        except (ClientError, BotoCoreError) as e:
            console.print(f"[red]Error deleting record: {e}[/red]")
            raise


def format_record_line(record: Dict[str, Any]) -> str:
    """Format a DNS record as a single line string."""
    name = record['Name']
    record_type = record['Type']
    ttl = record.get('TTL', 'N/A')
    
    # Extract values
    if 'ResourceRecords' in record:
        values = ', '.join([rr['Value'] for rr in record['ResourceRecords']])
    elif 'AliasTarget' in record:
        values = f"ALIAS -> {record['AliasTarget']['DNSName']}"
    else:
        values = "N/A"
    
    return f"{name:<50} {record_type:<10} TTL:{ttl:<6} {values}"


@app.command()
def list_zones():
    """List all hosted zones and their DNS records."""
    manager = Route53Manager()
    
    try:
        zones = manager.list_hosted_zones()
        
        if not zones:
            console.print("[yellow]No hosted zones found.[/yellow]")
            return
        
        for zone in zones:
            zone_id = zone['Id'].split('/')[-1]
            zone_name = zone['Name']
            record_count = zone['ResourceRecordSetCount']
            
            console.print(f"\n[bold cyan]Zone: {zone_name}[/bold cyan]")
            console.print(f"[dim]ID: {zone_id} | Records: {record_count}[/dim]")
            console.print("[dim]" + "─" * 100 + "[/dim]")
            
            records = manager.list_resource_records(zone_id)
            for record in records:
                console.print(format_record_line(record))
        
        console.print(f"\n[green]Total zones: {len(zones)}[/green]")
        
    except Exception as e:
        console.print(f"[red]Failed to list zones: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def add_record(
    zone_id: str = typer.Argument(..., help="Hosted Zone ID"),
    name: str = typer.Argument(..., help="Record name (e.g., www.example.com)"),
    record_type: str = typer.Argument(..., help="Record type (A, AAAA, CNAME, MX, TXT, etc.)"),
    value: str = typer.Argument(..., help="Record value"),
    ttl: int = typer.Option(300, help="TTL in seconds"),
):
    """Add a DNS record to a hosted zone."""
    manager = Route53Manager()
    
    try:
        console.print(f"[yellow]Adding record to zone {zone_id}...[/yellow]")
        response = manager.add_record(zone_id, name, record_type, value, ttl)
        
        change_id = response['ChangeInfo']['Id']
        status = response['ChangeInfo']['Status']
        
        console.print(f"[green]✓ Record added successfully![/green]")
        console.print(f"[dim]Change ID: {change_id}[/dim]")
        console.print(f"[dim]Status: {status}[/dim]")
        
    except Exception as e:
        console.print(f"[red]Failed to add record: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def remove_record(
    zone_id: str = typer.Argument(..., help="Hosted Zone ID"),
    name: str = typer.Argument(..., help="Record name (e.g., www.example.com)"),
    record_type: str = typer.Argument(..., help="Record type (A, AAAA, CNAME, MX, TXT, etc.)"),
    value: str = typer.Argument(..., help="Record value"),
    ttl: int = typer.Option(300, help="TTL in seconds"),
):
    """Remove a DNS record from a hosted zone."""
    manager = Route53Manager()
    
    try:
        console.print(f"[yellow]Removing record from zone {zone_id}...[/yellow]")
        response = manager.delete_record(zone_id, name, record_type, value, ttl)
        
        change_id = response['ChangeInfo']['Id']
        status = response['ChangeInfo']['Status']
        
        console.print(f"[green]✓ Record removed successfully![/green]")
        console.print(f"[dim]Change ID: {change_id}[/dim]")
        console.print(f"[dim]Status: {status}[/dim]")
        
    except Exception as e:
        console.print(f"[red]Failed to remove record: {e}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
