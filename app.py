#!/usr/bin/env python3
"""
Main entry point for Election Volunteer Signup Processor.

Usage:
    python app.py process                    # Process signups (default)
    python app.py validate                   # Run validation only
    python app.py report                     # Generate reports
    python app.py dashboard                  # Generate HTML dashboard
    python app.py --no-backups               # Skip backup assignments
    python app.py --auto-guess-threshold=3   # Set affinity threshold
    python app.py --output-format=html       # Generate HTML reports
"""
import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from main_processor import process
from volunteer_utils import generate_volunteer_suggestions
from reporting import generate_needs_report, generate_dashboard


def setup_logging(verbose=False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('app.log')
        ]
    )
    return logging.getLogger(__name__)


def validate_command(args, project_root, logger):
    """Run validation only."""
    logger.info("Running validation...")
    
    # Import validation module
    sys.path.insert(0, str(project_root / "tests"))
    try:
        from validate_location_matching import main as validate_main
        validate_main()
    except ImportError:
        logger.error("Validation script not found. Run from tests/validate_location_matching.py")
        return 1
    
    return 0


def process_command(args, project_root, logger):
    """Process volunteer signups."""
    logger.info("Starting signup processing...")
    
    config = {
        'include_backups': not args.no_backups,
        'fuzzy_threshold': args.fuzzy_threshold
    }
    
    try:
        results = process(project_root, config)
        logger.info(f"Processing complete!")
        logger.info(f"  Volunteers: {results['volunteer_count']}")
        logger.info(f"  Assignment rows: {results['assignment_rows']}")
        logger.info(f"  Duplicates resolved: {results['duplicates_resolved']}")
        
        # Generate auto-suggestions if requested
        if args.auto_guess_threshold > 0:
            logger.info(f"Generating volunteer suggestions (threshold: {args.auto_guess_threshold})...")
            suggestion_files = generate_volunteer_suggestions(project_root, args.auto_guess_threshold)
            if suggestion_files:
                for key, path in suggestion_files.items():
                    logger.info(f"  {key}: {path}")
        
        # Generate needs report
        if args.output_format in ['csv', 'html', 'markdown']:
            logger.info(f"Generating needs report ({args.output_format})...")
            report_path = generate_needs_report(project_root, args.output_format)
            if report_path:
                logger.info(f"  Report: {report_path}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        return 1


def report_command(args, project_root, logger):
    """Generate reports only."""
    logger.info("Generating reports...")
    
    # Generate needs report
    report_path = generate_needs_report(project_root, args.output_format)
    if report_path:
        logger.info(f"Needs report: {report_path}")
    
    # Generate suggestions
    if args.auto_guess_threshold > 0:
        suggestion_files = generate_volunteer_suggestions(project_root, args.auto_guess_threshold)
        if suggestion_files:
            for key, path in suggestion_files.items():
                logger.info(f"{key}: {path}")
    
    return 0


def dashboard_command(args, project_root, logger):
    """Generate HTML dashboard."""
    logger.info("Generating dashboard...")
    
    dashboard_path = generate_dashboard(project_root)
    if dashboard_path:
        logger.info(f"Dashboard: {dashboard_path}")
        return 0
    else:
        logger.error("Failed to generate dashboard")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description='Election Volunteer Signup Processor',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python app.py                    # Process signups with defaults
  python app.py validate           # Check location matching
  python app.py report             # Generate reports only
  python app.py dashboard          # Generate HTML dashboard
  python app.py --no-backups       # Skip backup assignments
  python app.py --verbose          # Enable debug logging
        """
    )
    
    parser.add_argument(
        'mode',
        nargs='?',
        default='process',
        choices=['process', 'validate', 'report', 'dashboard'],
        help='Operation mode (default: process)'
    )
    
    parser.add_argument(
        '--no-backups',
        action='store_true',
        help='Skip generating backup assignments'
    )
    
    parser.add_argument(
        '--check-precincts-only',
        action='store_true',
        help='Only validate precinct matching (alias for validate mode)'
    )
    
    parser.add_argument(
        '--auto-guess-threshold',
        type=int,
        default=5,
        help='Minimum signups for auto-suggestion (default: 5, 0 to disable)'
    )
    
    parser.add_argument(
        '--output-format',
        choices=['csv', 'html', 'markdown'],
        default='csv',
        help='Report output format (default: csv)'
    )
    
    parser.add_argument(
        '--fuzzy-threshold',
        type=int,
        default=85,
        help='Fuzzy matching threshold 0-100 (default: 85)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose/debug logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    # Get project root
    project_root = Path(__file__).parent
    
    logger.info(f"Starting in {args.mode} mode")
    
    # Route to appropriate command
    if args.check_precincts_only or args.mode == 'validate':
        return validate_command(args, project_root, logger)
    elif args.mode == 'process':
        return process_command(args, project_root, logger)
    elif args.mode == 'report':
        return report_command(args, project_root, logger)
    elif args.mode == 'dashboard':
        return dashboard_command(args, project_root, logger)
    else:
        logger.error(f"Unknown mode: {args.mode}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
