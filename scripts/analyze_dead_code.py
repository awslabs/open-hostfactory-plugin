#!/usr/bin/env python3
"""Analyze dead code in template system for Phase 2 cleanup."""

import os
import ast
import re
from typing import List, Dict, Set
from pathlib import Path

class TemplateDeadCodeAnalyzer:
    """Analyze template-related dead code for cleanup."""
    
    def __init__(self, src_path: str = "src"):
        self.src_path = Path(src_path)
        self.template_files = []
        self.dead_code_candidates = []
        self.duplicate_logic = []
        
    def analyze(self):
        """Run complete dead code analysis."""
        print("🔍 ANALYZING TEMPLATE DEAD CODE")
        print("=" * 50)
        
        self._find_template_files()
        self._analyze_domain_services()
        self._analyze_duplicate_caching_logic()
        self._analyze_unused_imports()
        self._analyze_large_classes()
        
        self._generate_cleanup_plan()
        
    def _find_template_files(self):
        """Find all template-related files."""
        for file_path in self.src_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'template' in content.lower() or 'Template' in content:
                        self.template_files.append(file_path)
            except Exception as e:
                print(f"Warning: Could not read {file_path}: {e}")
        
        print(f"📁 Found {len(self.template_files)} template-related files")
    
    def _analyze_domain_services(self):
        """Analyze domain services that should be replaced by CQRS."""
        domain_services = list(self.src_path.glob("domain/**/*service*.py"))
        
        print(f"\n🏗️ DOMAIN SERVICES ANALYSIS:")
        print(f"Found {len(domain_services)} domain service files")
        
        for service_file in domain_services:
            print(f"  📄 {service_file}")
            
            # Check if it's used in CQRS handlers
            if self._is_service_replaced_by_cqrs(service_file):
                self.dead_code_candidates.append({
                    'file': service_file,
                    'reason': 'Replaced by CQRS handlers',
                    'type': 'domain_service'
                })
    
    def _analyze_duplicate_caching_logic(self):
        """Analyze duplicate caching logic in template infrastructure."""
        cache_files = [
            "src/infrastructure/template/cache.py",
            "src/infrastructure/template/caching_ami_resolver.py", 
            "src/infrastructure/template/ami_cache.py"
        ]
        
        print(f"\n💾 CACHING LOGIC ANALYSIS:")
        
        cache_methods = {}
        for cache_file in cache_files:
            file_path = Path(cache_file)
            if file_path.exists():
                methods = self._extract_methods(file_path)
                cache_methods[cache_file] = methods
                print(f"  📄 {cache_file}: {len(methods)} methods")
        
        # Find duplicate method patterns
        all_methods = []
        for file, methods in cache_methods.items():
            all_methods.extend([(file, method) for method in methods])
        
        # Look for similar method names (potential duplicates)
        method_names = [method[1] for method in all_methods]
        duplicates = self._find_similar_names(method_names)
        
        if duplicates:
            print(f"  ⚠️  Found {len(duplicates)} potential duplicate method patterns")
            self.duplicate_logic.extend(duplicates)
    
    def _analyze_unused_imports(self):
        """Analyze unused template imports."""
        print(f"\n📦 IMPORT ANALYSIS:")
        
        unused_imports = []
        for file_path in self.template_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find template-related imports
                template_imports = re.findall(r'from.*template.*import.*|import.*template.*', content, re.IGNORECASE)
                
                for import_line in template_imports:
                    # Simple heuristic: if import is only used once (in the import line), it might be unused
                    imported_items = self._extract_imported_items(import_line)
                    for item in imported_items:
                        usage_count = content.count(item)
                        if usage_count <= 1:  # Only appears in import line
                            unused_imports.append({
                                'file': file_path,
                                'import': import_line,
                                'item': item
                            })
            except Exception as e:
                print(f"Warning: Could not analyze imports in {file_path}: {e}")
        
        print(f"  📊 Found {len(unused_imports)} potentially unused template imports")
        
    def _analyze_large_classes(self):
        """Analyze large classes that violate SRP."""
        print(f"\n📏 LARGE CLASS ANALYSIS:")
        
        large_classes = []
        for file_path in self.template_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                        if len(methods) > 10:  # Arbitrary threshold
                            large_classes.append({
                                'file': file_path,
                                'class': node.name,
                                'methods': len(methods),
                                'reason': 'Potential SRP violation'
                            })
            except Exception as e:
                print(f"Warning: Could not analyze {file_path}: {e}")
        
        for large_class in large_classes:
            print(f"  📄 {large_class['file']}: {large_class['class']} ({large_class['methods']} methods)")
        
        self.dead_code_candidates.extend(large_classes)
    
    def _generate_cleanup_plan(self):
        """Generate cleanup plan based on analysis."""
        print(f"\n📋 CLEANUP PLAN GENERATED:")
        print("=" * 50)
        
        print(f"🗑️  Dead code candidates: {len(self.dead_code_candidates)}")
        for candidate in self.dead_code_candidates:
            print(f"  - {candidate['file']}: {candidate['reason']}")
        
        print(f"\n🔄 Duplicate logic found: {len(self.duplicate_logic)}")
        for duplicate in self.duplicate_logic:
            print(f"  - {duplicate}")
        
        # Write cleanup plan to file
        with open("template_cleanup_plan.txt", "w") as f:
            f.write("TEMPLATE SYSTEM CLEANUP PLAN\n")
            f.write("=" * 40 + "\n\n")
            
            f.write("DEAD CODE CANDIDATES:\n")
            for candidate in self.dead_code_candidates:
                f.write(f"- {candidate['file']}: {candidate['reason']}\n")
            
            f.write(f"\nDUPLICATE LOGIC:\n")
            for duplicate in self.duplicate_logic:
                f.write(f"- {duplicate}\n")
        
        print(f"\n✅ Cleanup plan written to template_cleanup_plan.txt")
    
    def _is_service_replaced_by_cqrs(self, service_file: Path) -> bool:
        """Check if domain service is replaced by CQRS handlers."""
        # Simple heuristic: if there are corresponding CQRS handlers, service might be redundant
        service_name = service_file.stem
        
        # Look for corresponding handlers
        handler_files = list(self.src_path.glob("application/**/handlers.py"))
        for handler_file in handler_files:
            try:
                with open(handler_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if service_name.replace('_service', '').replace('service', '') in content.lower():
                        return True
            except Exception:
                pass
        
        return False
    
    def _extract_methods(self, file_path: Path) -> List[str]:
        """Extract method names from Python file."""
        methods = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    methods.append(node.name)
        except Exception as e:
            print(f"Warning: Could not extract methods from {file_path}: {e}")
        
        return methods
    
    def _find_similar_names(self, names: List[str]) -> List[str]:
        """Find similar method names that might indicate duplication."""
        similar = []
        for i, name1 in enumerate(names):
            for name2 in names[i+1:]:
                if self._are_similar(name1, name2):
                    similar.append(f"{name1} ~ {name2}")
        return similar
    
    def _are_similar(self, name1: str, name2: str) -> bool:
        """Check if two names are similar (simple heuristic)."""
        # Remove common prefixes/suffixes
        clean1 = name1.replace('get_', '').replace('set_', '').replace('_cache', '').replace('cache_', '')
        clean2 = name2.replace('get_', '').replace('set_', '').replace('_cache', '').replace('cache_', '')
        
        return clean1 == clean2 and name1 != name2
    
    def _extract_imported_items(self, import_line: str) -> List[str]:
        """Extract imported items from import line."""
        items = []
        if 'import' in import_line:
            # Simple regex to extract imported names
            matches = re.findall(r'import\s+([^,\s]+)', import_line)
            items.extend(matches)
            
            # Handle 'from ... import ...' format
            from_match = re.search(r'from.*import\s+(.+)', import_line)
            if from_match:
                import_part = from_match.group(1)
                items.extend([item.strip() for item in import_part.split(',')])
        
        return items

if __name__ == "__main__":
    analyzer = TemplateDeadCodeAnalyzer()
    analyzer.analyze()
