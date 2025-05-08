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
            "class_declaration": self.class_declaration,
            "public_field_definition": self.public_field_definition,
            "method_definition": self.method_declaration,

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
            "assignment_pattern": self.assignment_expression,
            # "assignment_pattern" is a special case of "assignment_expression
            "function_expression": self.method_declaration,
            "binary_expression": self.binary_expression,
            "member_expression": self.member_expression,
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
            "return_statement": self.return_statement,

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
            self.parse(child, statements, replacement)

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

    # 解析object.property形式
    def parse_field(self, node: Node, statements: list):
        myobject = self.find_child_by_field(node, "object")
        field = self.find_child_by_field(node, "property")
        shadow_object = self.parse(myobject, statements)
        shadow_field = self.parse(field, statements)
        return (shadow_object, shadow_field)

    def parse_type_annotation(self, type_node: Node):
        if type_node and (type_node.type == 'type_annotation' or type_node.type == 'predefined_type'):
            actual_type_text_parts = []
            start_collecting = False
            if type_node.type == 'predefined_type':
                start_collecting = True  
                actual_type_text_parts.append(self.read_node_text(type_node))
            else:
                # For type_annotation, skip the ':'
                for child in type_node.children:
                    if start_collecting:
                        actual_type_text_parts.append(self.read_node_text(child))
                    elif self.read_node_text(child) == ':':
                        start_collecting = True

            type_str = "".join(actual_type_text_parts).strip()
            return type_str if type_str else None
        elif type_node:  # Handle cases where type is directly given (e.g. in `as` cast)
            return self.read_node_text(type_node).strip()
        return None

    def parse_modifiers(self, node: Node):
        DIRECT_ATTR_KEYWORDS = {
            "public", "private", "protected",  
            "static", "abstract", "readonly",
            "async", "override",
            "declare",  
            "export",  
            "default",  
        }
        collected_attrs = set()

        for child in node.children:
            if child.type in DIRECT_ATTR_KEYWORDS:
                collected_attrs.add(child.type)
            elif child.type == 'accessibility_modifier':
                mod_text = self.read_node_text(child)
                if mod_text in DIRECT_ATTR_KEYWORDS:
                    collected_attrs.add(mod_text)

        parent = node.parent
        if parent:
            if parent.type == 'export_statement':
                collected_attrs.add('export')
                for child in parent.children:
                    if child.type == 'default':
                        collected_attrs.add('default')
                        break  
            current = node
            while current.parent:
                ancestor = current.parent
                if ancestor.type == 'ambient_declaration':
                    has_declare_keyword = any(child.type == 'declare' for child in ancestor.children)
                    if has_declare_keyword:
                        collected_attrs.add('declare')
                        break  
                if ancestor.type in ['export_statement', 'program', 'module']:
                    break
                current = ancestor

        return sorted(list(collected_attrs)) if collected_attrs else None

    def assignment_expression(self, node: Node, statements: list):
        # week2任务
        # week3任务，需要支持left为object.property的形式，可以用parser_field函数帮助解析
        # week3任务: 支持 object.property 左值

        left_node = node.child_by_field_name("left")
        right_node = node.child_by_field_name("right")

        if not left_node or not right_node:
            return None  
        value = self.parse(right_node, statements)

        if left_node.type == "member_expression" or left_node.type == "subscript_expression":
            parsed_field_result = self.parse_field(left_node, statements)
            if parsed_field_result is None or parsed_field_result == (None, None):
                return None  

            shadow_object, shadow_field = parsed_field_result

            stmt = {
                "field_write": {
                    "receiver_object": shadow_object,
                    "field": shadow_field,
                    "source": value,
                }
            }
            statements.append(stmt)
            return value

        elif self.is_identifier(left_node) or left_node.type == "private_property_identifier":
            target = self.read_node_text(left_node)

            stmt = {
                "assign_stmt": {
                    "target": target,
                    "operand": value,  
                }
            }
            statements.append(stmt)
            return value

        else:
            self.parse(left_node, statements)
            return value  # Still return RHS value

    def method_declaration(self, node, statements):
        # week2任务
        # week3任务，需要支持参数，可以用formal_parameter函数帮助解析
        # 函数名
        # week2 & week3任务: 支持简单参数与类型
        name_node = node.child_by_field_name("name")
        fallback_name = f"<{node.type}_{node.start_byte}_{node.end_byte}>"
        func_name = self.read_node_text(name_node) if name_node else fallback_name
        if node.type == 'method_definition' and func_name == 'constructor':
            pass  

        # 修饰符 attrs (Modifiers)
        attrs = self.parse_modifiers(node)  
        params_node = node.child_by_field_name("parameters")
        params_gir_list = []  
        if params_node and params_node.type == 'formal_parameters':  
            for param_node in params_node.named_children:
                parameter_info = self.formal_parameter(param_node, statements)  
                if parameter_info:
                    params_gir_list.append(parameter_info)
        # 返回值类型 data_type 
        return_type_node = node.child_by_field_name("return_type")
        data_type = self.parse_type_annotation(return_type_node)

        body_stmts: list = []
        body_node = node.child_by_field_name("body")
        if body_node is not None:
            if body_node.type == 'statement_block':
                self.statement_block(body_node, body_stmts)  
            elif node.type == 'arrow_function' and self.is_expression(body_node):
                result_expr = self.parse(body_node, body_stmts)
                body_stmts.append({"return_stmt": {"value": result_expr}})  
            elif node.type in ('method_signature', 'function_signature', 'abstract_method_signature'):
                pass  
        gir_key = node.type
        func_ir = {
            gir_key: {
                "attrs": attrs,
                "data_type": data_type,  
                "name": func_name,
                "parameters": params_gir_list,  
                "body": body_stmts,
            }
        }
        statements.append(func_ir)
        return func_name

    def formal_parameter(self, node: Node, statements: list):
        """ Parses a single simple formal parameter (name and optional type). statements not used. """
        # week3任务，解析参数
        # Handles nodes like 'required_parameter' or just 'identifier' within 'formal_parameters'.

        param_name = None
        data_type = None
        name_node = None
        type_node = None

        if node.type == 'required_parameter':
            name_node = node.child_by_field_name("pattern")  
            type_node = node.child_by_field_name("type")
        elif node.type == 'identifier':  
            name_node = node
            type_node = None  


        if name_node:
            if name_node.type == 'identifier' or name_node.type == 'this':
                param_name = self.read_node_text(name_node)
            elif name_node.type in ('object_pattern', 'array_pattern'):
                return None  
            else:  
                param_name = self.read_node_text(name_node)

        if type_node is None and node.type != 'identifier':  
            type_node = node.child_by_field_name("type")
        data_type = self.parse_type_annotation(type_node)

        if param_name:
            return {
                "parameter_decl": {
                    "name": param_name,
                    "data_type": data_type,
                }

            }

        return None  
    def class_declaration(self, node: Node, statements: list):
        # week3任务，解析class,class_body部分可用class_body函数帮助解析
        name_node = node.child_by_field_name("name")
        body_node = node.child_by_field_name("body")

        class_name = self.read_node_text(name_node) if name_node else f"<anonymous_class_{node.start_byte}>"

        attrs = self.parse_modifiers(node)

        fields_gir = []  
        methods_gir = []  

        if body_node and body_node.type == "class_body":
            self.class_body(body_node, fields_gir, methods_gir)

        class_ir = {
            "class_decl": {
                "name": class_name,
                "attrs": attrs,  
                "fields": fields_gir,  
                "member_methods": methods_gir,  
            }
        }

        statements.append(class_ir)
        return class_name

    def class_body(self, node, fields_list: list, methods_list: list):
        # week3任务，解析class_body部分，需要解析类的字段与成员函数
        for member in node.named_children:  
            if self.is_comment(member):
                continue

            if member.type == "method_definition":
                self.method_declaration(member, methods_list)
            elif member.type == "public_field_definition" or member.type == "field_definition":
                self.public_field_definition(member, fields_list)
            else:
                pass

    def public_field_definition(self, node: Node, statements: list):
        # week3任务, 解析类的字段
        name_node = node.child_by_field_name("name")
        type_node = node.child_by_field_name("type")
        value_node = node.child_by_field_name("value") 
        field_name = self.read_node_text(name_node) if name_node else f"<unknown_field_{node.start_byte}>"

        attrs = self.parse_modifiers(node)

        data_type = self.parse_type_annotation(type_node)

        value = self.parse(value_node, statements) if value_node else None

        field_ir = {
            "variable_decl": {
                "name": field_name,
                "attrs": attrs,  
                "data_type": data_type,
                "value": value,  
            }
        }
        statements.append(field_ir)
        return field_name

    def member_expression(self, node: Node, statements: list, flag=0):
        obj = self.parse(self.find_child_by_field(node, "object"), statements)
        property_ = self.parse(self.find_child_by_field(node, "property"), statements)
        tmp_var = self.tmp_variable(node)
        statements.append({"field_read": {"target": tmp_var, "receiver_object": obj, "field": property_}})
        return tmp_var

    def binary_expression(self, node: Node, statements: list):
        operator = self.find_child_by_field(node, "operator")
        shadow_operator = self.read_node_text(operator)
        right = self.find_child_by_field(node, "right")
        shadow_right = self.parse(right, statements)
        left = self.find_child_by_field(node, "left")
        shadow_left = self.parse(left, statements)

        tmp_var = self.tmp_variable(node)
        statements.append({"assign_stmt": {"target": tmp_var, "operator": shadow_operator, "operand": shadow_left,
                                           "operand2": shadow_right}})
        return tmp_var

    def return_statement(self, node: Node, statements: list):
        shadow_name = ""
        if node.named_child_count > 0:
            name = node.named_children[0]
            shadow_name = self.parse(name, statements)

        statements.append({"return_stmt": {"name": shadow_name}})
        return shadow_name

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