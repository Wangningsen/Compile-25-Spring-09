#!/usr/bin/env python3

from tree_sitter import Node
from . import common_parser

class Parser(common_parser.Parser):
    def is_comment(self, node):
        return node.type in ["line_comment", "block_comment"]

    def is_identifier(self, node):
        return node.type == "identifier"

    def obtain_literal_handler(self, node):
        LITERAL_MAP = {
            "null": self.regular_literal,
            "true": self.regular_literal,
            "false": self.regular_literal,
            "identifier": self.regular_literal,
            "number": self.regular_number_literal,
            "string": self.string_literal,
            "summary_string": self.string_literal,
            "summary_substitution": self.string_substitution,
            "this": self.this_literal,
            "super": self.super_literal,
            "private_property_identifier": self.regular_literal,
            "property_identifier": self.regular_literal
        }

        return LITERAL_MAP.get(node.type, None)

    def is_literal(self, node):
        return self.obtain_literal_handler(node) is not None

    def literal(self, node: Node, statements: list, replacement: list):
        handler = self.obtain_literal_handler(node)
        return handler(node, statements, replacement)

    def check_declaration_handler(self, node):
        DECLARATION_HANDLER_MAP = {
            "function_declaration": self.method_declaration,
            "method_signature": self.method_declaration,
            "function_signature": self.method_declaration,
        }
        return DECLARATION_HANDLER_MAP.get(node.type, None)

    def is_declaration(self, node):
        return self.check_declaration_handler(node) is not None

    def declaration(self, node: Node, statements: list):
        handler = self.check_declaration_handler(node)
        return handler(node, statements)

    def check_expression_handler(self, node):
        EXPRESSION_HANDLER_MAP = {
            "assignment_expression": self.assignment_expression,
            "assignment_pattern": self.assignment_expression,  # "assignment_pattern" is a special case of "assignment_expression
            "function_expression": self.method_declaration,
        }

        return EXPRESSION_HANDLER_MAP.get(node.type, None)

    def is_expression(self, node):
        return self.check_expression_handler(node) is not None

    def expression(self, node: Node, statements: list):
        handler = self.check_expression_handler(node)
        return handler(node, statements)

    def check_statement_handler(self, node):
        STATEMENT_HANDLER_MAP = {
            "statement_block": self.statement_block,
        }
        return STATEMENT_HANDLER_MAP.get(node.type, None)

    def is_statement(self, node):
        return self.check_statement_handler(node) is not None

    def statement(self, node: Node, statements: list):
        handler = self.check_statement_handler(node)
        return handler(node, statements)

    def string_literal(self, node: Node, statements: list, replacement: list):
        replacement = []
        for child in node.named_children:
            self.parse(child,statements,replacement)

        ret = self.read_node_text(node)
        if replacement:
            for r in replacement:
                (expr, value) = r
                ret = ret.replace(self.read_node_text(expr), value)

        ret = self.handle_hex_string(ret)
        return self.handle_hex_string(ret)

    def string_substitution(self, node: Node, statements: list, replacement: list):
        expr = node.named_children[0]
        shadow_expr = self.parse(expr, statements)
        replacement.append((node, shadow_expr))
        return shadow_expr

    def this_literal(self, node: Node, statements: list, replacement: list):
        return self.global_this()

    def super_literal(self, node: Node, statements: list, replacement: list):
        return self.global_super()

    def regular_literal(self, node: Node, statements: list, replacement: list):
        return self.read_node_text(node)
    
    def regular_number_literal(self, node: Node, statements: list, replacement: list):
        value = self.read_node_text(node)
        value = self.common_eval(value)
        return str(value)
    
    def non_null_expression(self, node: Node, statements: list):
        self.parse(node.named_children[0], statements)

    def assignment_expression(self, node: Node, statements: list):
        # week2 assignment
        # Tree‑sitter JavaScript / TypeScript 语法：
        # (assignment_expression
        #     left:  <node>
        #     operator: "="
        #     right: <node>)
        print(">>> hit assignment_expression", node.type)
        left_node  = node.child_by_field_name("left")  or node.named_children[0]
        right_node = node.child_by_field_name("right") or node.named_children[-1]

        # 只允许 identifier / literal
        if not (self.is_identifier(left_node) or self.is_literal(left_node)):
            return                          # 非简单左值：跳过
        if not (self.is_identifier(right_node) or self.is_literal(right_node)):
            return                          # 非简单右值：跳过

        target = self.read_node_text(left_node)
        value  = self.parse(right_node, statements)    # 调父类解析，保证字符串字面量等被处理

        # 生成中间表示
        stmt = {
            "assign_stmt": {
                "target": target,
                "oprand":  value,
            }
        }
        statements.append(stmt)
        return target        


    def pattern(self, node: Node, statements: list):
        return self.parse(self.node.named_children[0], statements)


    def parse_private_property_identifier(self, node: Node, statements: list):
            return self.read_node_text(node)

    def parse_sequence_expression(self, node: Node, statements: list):
        sub_expressions = node.named_children
        sequence_list = []
        for sub_expression in sub_expressions:
            if self.is_comment(sub_expression):
                continue
            sequence_list.append(self.parse(sub_expression, statements))
        return sequence_list

    def method_declaration(self, node: Node, statements: list):
        """解析 function_declaration / method_signature / function_signature / method_definition etc.

        根据 tree-sitter AST 节点 (node) 提取信息，并构建 GIR 结构添加到 statements 列表中。
        同时考虑父节点上下文来确定 export/declare 状态。

        产出结构 (添加到 statements):
        {
            <node_type>: {  # e.g., "function_declaration" or "method_definition"
                "attrs":      ["public", "static", ...],   # Sorted list of attributes/modifiers
                "data_type":  "number" | "void" | None,    # Return type string or None
                "name":       "foo" | "<anonymous>",       # Function/Method name
                "body":       [...],                       # List of parsed statements in the body
            }
        }
        """
        # ─────────────────────────────────────────────────────────────
        # 1. 函数名 (Function Name)
        # ─────────────────────────────────────────────────────────────
        name_node = node.child_by_field_name("name")
        # Use node's type and start byte as part of a fallback name if identifier is missing
        fallback_name = f"<{node.type}_{node.start_byte}>"
        func_name = self.read_node_text(name_node) if name_node else fallback_name


        # ─────────────────────────────────────────────────────────────
        # 2. 修饰符 attrs (Modifiers)
        # ─────────────────────────────────────────────────────────────
        # Keywords that appear as direct children modifiers of the function/method node itself
        # Based on grammar analysis (e.g., method_definition includes these)
        DIRECT_ATTR_KEYWORDS = {
            "public", "private", "protected",  # From accessibility_modifier choice
            "static", "abstract", "readonly",
            "async", "override",
            # 'get', 'set' could be added if needing to differentiate getters/setters
        }
        collected_attrs = set()

        # 2.1 Process direct children for applicable modifiers
        for child in node.children:
            if child.is_named:
                if child.type in DIRECT_ATTR_KEYWORDS:
                    # Use the node type string itself as the attribute name
                    collected_attrs.add(child.type)
                # Handle accessibility_modifier case IF tree-sitter creates 'accessibility_modifier' nodes
                # instead of nodes named 'public', 'private', etc. (Check your specific setup)
                # elif child.type == 'accessibility_modifier':
                #     attr_text = self.read_node_text(child) # Should be 'public', 'private', or 'protected'
                #     if attr_text in {"public", "private", "protected"}:
                #          collected_attrs.add(attr_text)

        # 2.2 Process parent context for export, default, declare
        parent = node.parent
        if parent:
            # Check if the direct parent is an export statement
            if parent.type == 'export_statement':
                collected_attrs.add('export')
                # Check children of the export_statement for 'default' keyword node
                for child in parent.children:
                    if child.type == 'default':
                        collected_attrs.add('default')
                        break # Found default, no need to look further

            # Check if the direct parent is an ambient declaration (for 'declare')
            # This check is independent of export status, covering cases like 'declare function'
            # and 'export declare function'.
            elif parent.type == 'ambient_declaration':
                 # Ensure the 'declare' keyword node is actually present as a child of the parent
                 # (Some ambient contexts might be implicit)
                 has_declare_keyword = False
                 for child in parent.children:
                     if child.type == 'declare':
                         has_declare_keyword = True
                         break
                 if has_declare_keyword:
                      collected_attrs.add('declare')

        # Convert the set of collected attributes to a sorted list for consistent GIR output
        attrs = sorted(list(collected_attrs)) if collected_attrs else None

        # ─────────────────────────────────────────────────────────────
        # 3. 返回值类型 data_type (Return Type)
        # ─────────────────────────────────────────────────────────────
        data_type = None
        # Common field names for return type nodes in JS/TS grammars
        type_node = node.child_by_field_name("return_type") or \
                    node.child_by_field_name("type") or \
                    node.child_by_field_name("type_annotation")

        if type_node is not None:
            # Type annotation nodes often include the ':' token, so get the actual type part
            actual_type_node = type_node
            # If the node itself is 'type_annotation', its first child might be ':'
            if type_node.type == 'type_annotation' and type_node.child_count > 0:
                 first_child = type_node.children[0]
                 if self.read_node_text(first_child) == ':':
                      # Find the actual type node(s) after the colon
                      if type_node.child_count > 1:
                           # Simplification: assume type is the rest of the text
                           # A more robust way involves getting the specific type node child
                           type_text_content = self.read_node_text(type_node) # Get full text ' : <type>'
                           if type_text_content:
                                data_type = type_text_content.lstrip(':').strip()
                           else:
                                data_type = None
                      else: # Only ':' found? Invalid annotation?
                           data_type = None
                 else: # Type annotation node doesn't start with ':', use its full text
                      data_type = self.read_node_text(type_node).strip()
            else: # Not a 'type_annotation' node, use its text directly
                data_type = self.read_node_text(type_node).strip()

            # Ensure empty string becomes None
            if not data_type:
                data_type = None


        # ─────────────────────────────────────────────────────────────
        # 4. 递归解析函数体 (Body)
        # ─────────────────────────────────────────────────────────────
        body_stmts: list = []
        body_node = node.child_by_field_name("body")
        if body_node is not None:
            # Standard function/method bodies are statement blocks
            if body_node.type == 'statement_block':
                 self.statement_block(body_node, body_stmts)
            # Arrow functions can have an expression as a body
            elif node.type == 'arrow_function' and body_node.is_named:
                 # Adapt this: You might want to parse the expression
                 # or store a representation of the expression body.
                 # For simplicity here, we'll try parsing it as if it were a block's content
                 # or add a placeholder. A dedicated expression parser would be better.
                 expr_body_placeholder = { "expression_body": self.read_node_text(body_node) }
                 body_stmts.append(expr_body_placeholder)
        elif node.type in ('method_signature', 'function_signature'):
            # Signatures intentionally have no body
            pass



        # ─────────────────────────────────────────────────────────────
        # 5. 组装 GIR 节点 (Assemble GIR Node)
        # ─────────────────────────────────────────────────────────────
        # Use the specific node type (e.g., "method_definition") as the key in the GIR
        gir_key = node.type
        func_ir = {
            gir_key: {
                "attrs":      attrs,
                "data_type":  data_type,
                "name":       func_name,
                "body":       body_stmts,
             }
        }
        statements.append(func_ir)

        # Return the function name, could be useful for caller
        return func_name



    def function_expression(self, node: Node, statements: list):
        return self.method_declaration(node, statements)





    def statement_block(self, node: Node, statements: list):
        children = node.named_children
        for child in children:
            if self.is_comment(child):
                continue
            self.parse(child, statements)



    def expression_statement(self, node: Node, statements: list):
        return self.parse(node.named_children[0], statements)
