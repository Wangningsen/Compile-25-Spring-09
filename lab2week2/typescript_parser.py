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
        # 函数名
        name_node = node.child_by_field_name("name")
        fallback_name = f"<{node.type}_{node.start_byte}>"
        func_name = self.read_node_text(name_node) if name_node else fallback_name


        #修饰符 attrs (Modifiers)
        DIRECT_ATTR_KEYWORDS = {
            "public", "private", "protected",  # From accessibility_modifier choice
            "static", "abstract", "readonly",
            "async", "override",
            # 'get', 'set' could be added if needing to differentiate getters/setters
        }
        collected_attrs = set()

        for child in node.children:
            if child.is_named:
                if child.type in DIRECT_ATTR_KEYWORDS:
                    collected_attrs.add(child.type)

        parent = node.parent
        if parent:
            if parent.type == 'export_statement':
                collected_attrs.add('export')
                for child in parent.children:
                    if child.type == 'default':
                        collected_attrs.add('default')
            elif parent.type == 'ambient_declaration':
                 has_declare_keyword = False
                 for child in parent.children:
                     if child.type == 'declare':
                         has_declare_keyword = True
                         break
                 if has_declare_keyword:
                      collected_attrs.add('declare')

        attrs = sorted(list(collected_attrs)) if collected_attrs else None

        # 返回值类型 data_type
        data_type = None
        type_node = node.child_by_field_name("return_type")

        if type_node is not None:
            if type_node.type == 'type_annotation':
                actual_type_text_parts = []
                found_colon = False

                for child in type_node.children:
                    if not found_colon:
                        if self.read_node_text(child) == ':':
                            found_colon = True
                            continue
                    

                    if found_colon:
                        actual_type_text_parts.append(self.read_node_text(child))

                if actual_type_text_parts:
                    data_type = "".join(actual_type_text_parts).strip()
        
        # Ensure empty string becomes None
        if not data_type:
            data_type = None

        # 递归解析函数体 (Body)
        body_stmts: list = []
        body_node = node.child_by_field_name("body")
        if body_node is not None:
            if body_node.type == 'statement_block':
                 self.statement_block(body_node, body_stmts)
            elif node.type == 'arrow_function' and body_node.is_named:
                 expr_body_placeholder = { "expression_body": self.read_node_text(body_node) }
                 body_stmts.append(expr_body_placeholder)
        elif node.type in ('method_signature', 'function_signature'):
            pass

        # 组装 GIR 节点
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
