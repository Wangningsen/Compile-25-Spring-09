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
                "value":  value,
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

    # def method_declaration(self,node,statements):
    #     #week2 assignment
    #     print(">>> hit method_declaration", node.type)
    #     name_node = node.child_by_field_name("name")
    #     func_name = self.read_node_text(name_node) if name_node else "<anonymous>"

    #     body_node = node.child_by_field_name("body")
    #     body_stmts: list = []

    #     # 递归解析函数体
    #     if body_node is not None:
    #         # body → statement_block；直接复用已有逻辑
    #         self.statement_block(body_node, body_stmts)

    #     func_ir = {
    #         "function_declaration": {
    #             "name": func_name,
    #             "body": body_stmts,            
    #         }

    #     }
    #     statements.append(func_ir)
    #     return func_name
    
    def method_declaration(self, node: Node, statements: list):
        """解析 function_declaration / method_signature / function_signature
        产出结构:
        {
            "function_declaration": {
                "attrs":      ["public", "static", ...],   # 没有就空列表
                "data_type":  "number" | "void" | None,    # 没有返回类型标注就 None
                "name":       "foo",
                "body":       [...],                       # 递归得到的内部语句列表
            }
        }
        """
        # ─────────────────────────────────────────────────────────────
        # 1. 函数名
        # ─────────────────────────────────────────────────────────────
        name_node  = node.child_by_field_name("name")
        func_name  = self.read_node_text(name_node) if name_node else "<anonymous>"

        # ─────────────────────────────────────────────────────────────
        # 2. 修饰符 attrs（async / public / static / export …）
        #    tree‑sitter TypeScript 把这些词直接当作独立命名节点
        # ─────────────────────────────────────────────────────────────
        ATTR_KEYWORDS = {
            "public", "private", "protected",
            "static", "abstract", "readonly",
            "async", "export", "default", "declare"
        }
        attrs = [
            self.read_node_text(child)
            for child in node.children
            if child.is_named and child.type in ATTR_KEYWORDS
        ]

        # ─────────────────────────────────────────────────────────────
        # 3. 返回值类型 data_type ⇒ 来自 type_annotation 节点
        #    形如  ":" <type>
        # ─────────────────────────────────────────────────────────────
        data_type = None
        type_node = node.child_by_field_name("return_type") \
                or node.child_by_field_name("type")         \
                or node.child_by_field_name("type_annotation")
        if type_node is not None:
            # 去掉前导冒号和空白
            data_type = self.read_node_text(type_node).lstrip(":").strip()

        # ─────────────────────────────────────────────────────────────
        # 4. 递归解析函数体
        # ─────────────────────────────────────────────────────────────
        body_stmts: list = []
        body_node = node.child_by_field_name("body")
        if body_node is not None:                 # 可能是接口声明，没有函数体
            self.statement_block(body_node, body_stmts)

        # ─────────────────────────────────────────────────────────────
        # 5. 组装 GIR 节点（嵌套式，兼容 flatten_stmt 约定）
        # ─────────────────────────────────────────────────────────────
        func_ir = {
            "function_declaration": {
                "attrs":     attrs,
                "data_type": data_type,
                "name":      func_name,
                "body":      body_stmts,
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
