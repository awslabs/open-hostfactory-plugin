#!/usr/bin/env python3
"""Analyze template dependencies for Phase 2 planning."""

import os
import re
import ast
from typing import Dict, List, Set
from pathlib import Path

class TemplateDependencyAnalyzer:
    """Analyze template-related dependencies."""
    
    def __init__(self, src_path: str = "src"):
        self.src_path = Path(src_path)
        self.dependencies = {}
        self.circular_deps = []
        self.di_registrations = []
        
    def analyze(self):
        """Run complete dependency analysis."""
        print("🔍 ANALYZING TEMPLATE DEPENDENCIES")
        print("=" * 50)
        
        self._analyze_import_dependencies()
        self._analyze_di_registrations()
        self._detect_circular_dependencies()
        self._analyze_template_infrastructure_deps()
        
        self._generate_dependency_report()
    
    def _analyze_import_dependencies(self):
        """Analyze import dependencies in template files."""
        print("📦 ANALYZING IMPORT DEPENDENCIES:")
        
        template_files = list(self.src_path.rglob("*.py"))
        
        for file_path in template_files:
            if 'template' in str(file_path).lower():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Extract imports
                    imports = self._extract_imports(content)
                    self.dependencies[str(file_path)] = imports
                    
                except Exception as e:
                    print(f"Warning: Could not analyze {file_path}: {e}")
        
        print(f"  📊 Analyzed {len(self.dependencies)} template files")
    
    def _analyze_di_registrations(self):
        """Analyze current DI registrations for template components."""
        print("\n🔧 ANALYZING DI REGISTRATIONS:")
        
        di_files = [
            "src/infrastructure/di/services.py",
            "src/infrastructure/di/container.py",
            "src/infrastructure/di/__init__.py"
        ]
        
        for di_file in di_files:
            file_path = Path(di_file)
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Find template-related registrations
                    template_registrations = re.findall(
                        r'register.*[Tt]emplate.*|[Tt]emplate.*register',
                        content,
                        re.MULTILINE
                    )
                    
                    if template_registrations:
                        print(f"  📄 {di_file}:")
                        for reg in template_registrations:
                            print(f"    - {reg.strip()}")
                            self.di_registrations.append({
                                'file': di_file,
                                'registration': reg.strip()
                            })
                
                except Exception as e:
                    print(f"Warning: Could not analyze {di_file}: {e}")
        
        if not self.di_registrations:
            print("  ⚠️  No template DI registrations found")
    
    def _detect_circular_dependencies(self):
        """Detect circular dependencies in template code."""
        print("\n🔄 DETECTING CIRCULAR DEPENDENCIES:")
        
        # Build dependency graph
        graph = {}
        for file_path, imports in self.dependencies.items():
            graph[file_path] = []
            for imp in imports:
                # Convert import to file path (simplified)
                if 'template' in imp.lower():
                    target_file = self._import_to_file_path(imp)
                    if target_file and target_file in self.dependencies:
                        graph[file_path].append(target_file)
        
        # Detect cycles using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node):
            if node in rec_stack:
                return True
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if has_cycle(neighbor):
                    return True
            
            rec_stack.remove(node)
            return False
        
        cycles_found = 0
        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    cycles_found += 1
                    self.circular_deps.append(node)
        
        if cycles_found > 0:
            print(f"  ⚠️  Found {cycles_found} potential circular dependencies")
            for dep in self.circular_deps:
                print(f"    - {dep}")
        else:
            print("  ✅ No circular dependencies detected")
    
    def _analyze_template_infrastructure_deps(self):
        """Analyze template infrastructure dependencies."""
        print("\n🏗️ ANALYZING TEMPLATE INFRASTRUCTURE DEPENDENCIES:")
        
        infrastructure_files = [
            "src/infrastructure/template/cache.py",
            "src/infrastructure/template/configuration_manager.py",
            "src/infrastructure/template/loader.py",
            "src/infrastructure/template/caching_ami_resolver.py"
        ]
        
        for inf_file in infrastructure_files:
            file_path = Path(inf_file)
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Count dependencies
                    imports = self._extract_imports(content)
                    external_deps = [imp for imp in imports if not imp.startswith('src.infrastructure.template')]
                    
                    print(f"  📄 {inf_file}:")
                    print(f"    - Total imports: {len(imports)}")
                    print(f"    - External dependencies: {len(external_deps)}")
                    
                    # Check for AWS-specific dependencies
                    aws_deps = [imp for imp in imports if 'aws' in imp.lower()]
                    if aws_deps:
                        print(f"    - AWS dependencies: {len(aws_deps)}")
                        for aws_dep in aws_deps:
                            print(f"      * {aws_dep}")
                
                except Exception as e:
                    print(f"Warning: Could not analyze {inf_file}: {e}")
    
    def _generate_dependency_report(self):
        """Generate dependency analysis report."""
        print(f"\n📋 DEPENDENCY ANALYSIS REPORT:")
        print("=" * 50)
        
        # Write detailed report
        with open("template_dependency_analysis.txt", "w") as f:
            f.write("TEMPLATE DEPENDENCY ANALYSIS REPORT\n")
            f.write("=" * 50 + "\n\n")
            
            f.write("IMPORT DEPENDENCIES:\n")
            for file_path, imports in self.dependencies.items():
                f.write(f"\n{file_path}:\n")
                for imp in imports:
                    f.write(f"  - {imp}\n")
            
            f.write(f"\nDI REGISTRATIONS:\n")
            for reg in self.di_registrations:
                f.write(f"- {reg['file']}: {reg['registration']}\n")
            
            f.write(f"\nCIRCULAR DEPENDENCIES:\n")
            for dep in self.circular_deps:
                f.write(f"- {dep}\n")
        
        print("✅ Dependency analysis report written to template_dependency_analysis.txt")
        
        # Summary
        print(f"\n📊 SUMMARY:")
        print(f"  - Template files analyzed: {len(self.dependencies)}")
        print(f"  - DI registrations found: {len(self.di_registrations)}")
        print(f"  - Circular dependencies: {len(self.circular_deps)}")
    
    def _extract_imports(self, content: str) -> List[str]:
        """Extract import statements from Python content."""
        imports = []
        
        # Find import statements
        import_patterns = [
            r'^from\s+([^\s]+)\s+import',
            r'^import\s+([^\s,]+)'
        ]
        
        for line in content.split('\n'):
            line = line.strip()
            for pattern in import_patterns:
                match = re.match(pattern, line)
                if match:
                    imports.append(match.group(1))
        
        return imports
    
    def _import_to_file_path(self, import_path: str) -> str:
        """Convert import path to file path (simplified)."""
        # Convert src.infrastructure.template.cache to src/infrastructure/template/cache.py
        if import_path.startswith('src.'):
            file_path = import_path.replace('.', '/') + '.py'
            if Path(file_path).exists():
                return file_path
        return None

if __name__ == "__main__":
    analyzer = TemplateDependencyAnalyzer()
    analyzer.analyze()
