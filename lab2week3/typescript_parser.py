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
            "assignment_pattern": self.assignment_expression,  # "assignment_pattern" is a special case of "assignment_expression
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
        """ Parses a type annotation node and returns the type string. """
        if type_node and (type_node.type == 'type_annotation' or type_node.type == 'predefined_type'):
                actual_type_text_parts = []
                start_collecting = False
                if type_node.type == 'predefined_type':
                    start_collecting = True # Directly use the text of predefined_type
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
        elif type_node: # Handle cases where type is directly given (e.g. in `as` cast)
                return self.read_node_text(type_node).strip()
        return None
    
    def parse_modifiers(self, node: Node):
        """ Parses modifiers (public, private, static, etc.) for declarations. """
        # Define keywords that represent modifiers recognized directly by their node type
        DIRECT_ATTR_KEYWORDS = {
            "public", "private", "protected",  # From accessibility_modifier choice
            "static", "abstract", "readonly",
            "async", "override",
            "declare", # Added declare
            "export", # Added export
            "default", # Added default
            # 'get', 'set' could be added if needing to differentiate accessors
        }
        collected_attrs = set()

        # 1. Check direct children of the node itself
        for child in node.children:
            if child.type in DIRECT_ATTR_KEYWORDS:
                collected_attrs.add(child.type)
            # Sometimes modifiers are wrapped, e.g., accessibility_modifier
            elif child.type == 'accessibility_modifier':
                mod_text = self.read_node_text(child)
                if mod_text in DIRECT_ATTR_KEYWORDS:
                    collected_attrs.add(mod_text)

        # 2. Check parent for context-dependent modifiers (export, default, declare)
        parent = node.parent
        if parent:
            # Check for 'export' and 'default'
            if parent.type == 'export_statement':
                collected_attrs.add('export')
                for child in parent.children:
                    if child.type == 'default':
                        collected_attrs.add('default')
                        break # Found default, no need to check further children of export_statement
            # Check for 'declare'
            # Traverse up in case of nested structures like export > declare > function
            current = node
            while current.parent:
                ancestor = current.parent
                if ancestor.type == 'ambient_declaration':
                    # Check if 'declare' keyword exists as a direct child of ambient_declaration
                    has_declare_keyword = any(child.type == 'declare' for child in ancestor.children)
                    if has_declare_keyword:
                            collected_attrs.add('declare')
                            break # Found declare context
                # Stop if we hit export or module level
                if ancestor.type in ['export_statement', 'program', 'module']:
                    break
                current = ancestor


        return sorted(list(collected_attrs)) if collected_attrs else None

    def assignment_expression(self, node: Node, statements: list):
        #week2任务
        #week3任务，需要支持left为object.property的形式，可以用parser_field函数帮助解析
        # week3任务: 支持 object.property 左值
        # Remove previous restrictive checks on left/right operands

        left_node = node.child_by_field_name("left")
        right_node = node.child_by_field_name("right")
        # operator_node = node.child_by_field_name("operator") # For compound assignment (optional)
        # op_text = self.read_node_text(operator_node) if operator_node else '='


        if not left_node or not right_node:
            # print(f"Warning: Skipping invalid assignment expression at {node.start_point}")
            return None # Or raise error

        # Parse the right side - the value being assigned
        value = self.parse(right_node, statements)

        # Check the type of the left side
        if left_node.type == "member_expression" or left_node.type == "subscript_expression":
            # Case: object.property = value OR object[property] = value
            # Use parse_field helper
            parsed_field_result = self.parse_field(left_node, statements)
            if parsed_field_result is None or parsed_field_result == (None, None):
                 # print(f"Warning: Could not parse field access in assignment LHS: {self.read_node_text(left_node)}")
                 return None # Failed to parse LHS field access

            shadow_object, shadow_field = parsed_field_result

            # Generate GIR for field write (simple assignment, ignore compound for now)
            stmt = {
                "field_write": {
                    "receiver_object": shadow_object,
                    "field": shadow_field,
                    "value": value,
                }
            }
            statements.append(stmt)
            # Assignment expressions usually evaluate to the assigned value
            return value

        elif self.is_identifier(left_node) or left_node.type == "private_property_identifier":
            # Case: variable = value
            target = self.read_node_text(left_node)

            # Generate GIR for variable assignment
            stmt = {
                "assign_stmt": {
                    "target": target,
                    "operand": value, # Renamed 'oprand' to 'operand' for consistency
                }
            }
            statements.append(stmt)
            # Return the assigned value
            return value

        else:
            # Handle other complex left-hand sides like destructuring if needed
            # For now, treat unrecognized LHS as skipped or parse for side effects
            # print(f"Warning: Skipping assignment with unhandled left-hand side type: {left_node.type}")
            # Parse LHS for potential side effects, but don't create assignment GIR
            self.parse(left_node, statements)
            return value # Still return RHS value 

    def method_declaration(self,node,statements):
        #week2任务
        #week3任务，需要支持参数，可以用formal_parameter函数帮助解析
                # 函数名
        # week2 & week3任务: 支持简单参数与类型
        name_node = node.child_by_field_name("name")
        fallback_name = f"<{node.type}_{node.start_byte}_{node.end_byte}>"
        func_name = self.read_node_text(name_node) if name_node else fallback_name
        if node.type == 'method_definition' and func_name == 'constructor':
             pass # Keep 'constructor' name

        #修饰符 attrs (Modifiers) - Use helper function
        attrs = self.parse_modifiers(node) # Handles public/private etc. for methods
        # --- Parameter Parsing (Refined Loop) ---
        params_node = node.child_by_field_name("parameters")
        params_gir_list = [] # Use a distinct name for the list
        if params_node and params_node.type == 'formal_parameters': # Check node type
            # Iterate through the actual parameter definition nodes inside formal_parameters
            # These children are typically 'required_parameter', 'optional_parameter', 'rest_parameter', etc.
            # Or sometimes just 'identifier' in simpler JS grammars.
            for param_node in params_node.named_children:
                # Directly call the dedicated formal_parameter function for each node
                parameter_info = self.formal_parameter(param_node, statements) # Pass the actual parameter node
                if parameter_info:
                    # Append the dictionary returned by formal_parameter
                    params_gir_list.append(parameter_info)
                # else: # Optional: Log parameters that couldn't be parsed by formal_parameter
                #    print(f"Debug: formal_parameter returned None for node: {param_node.type}")

        # --- End Parameter Parsing ---


        # 返回值类型 data_type - Use helper function
        return_type_node = node.child_by_field_name("return_type")
        data_type = self.parse_type_annotation(return_type_node)

        # 递归解析函数体 (Body) - Keep existing logic
        body_stmts: list = []
        body_node = node.child_by_field_name("body")
        if body_node is not None:
            if body_node.type == 'statement_block':
                self.statement_block(body_node, body_stmts) # Assumes statement_block exists
            # Handle arrow function expression body (non-block)
            elif node.type == 'arrow_function' and self.is_expression(body_node):
                 result_expr = self.parse(body_node, body_stmts)
                 # Add implicit return for arrow function expression body
                 body_stmts.append({"return_stmt": {"value": result_expr}}) # Use 'value' key
            # Method/Function signatures/abstract methods have no body
            elif node.type in ('method_signature', 'function_signature', 'abstract_method_signature'):
                 pass # No body to parse

        # 组装 GIR 节点
        gir_key = node.type
        func_ir = {
            gir_key: {
                "attrs": attrs,
                "data_type": data_type, # Return type
                "name": func_name,
                "parameters": params_gir_list, # Include parsed parameters
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

        # Find name and type nodes based on expected structures
        if node.type == 'required_parameter':
            # For required_parameter, the name is inside the 'pattern' field
            name_node = node.child_by_field_name("pattern") # Often an identifier
            type_node = node.child_by_field_name("type")
        elif node.type == 'identifier': # Simple JS-style parameter (name only)
            name_node = node
            type_node = None # No type annotation possible here in standard JS
        elif node.type == 'this_parameter': # Handle 'this' parameter in TS
             # Name is implicitly 'this'
             name_node = node.children[0] if node.children and node.children[0].type == 'this' else None
             type_node = node.child_by_field_name("type") # Type follows 'this'
        # Add elif for 'optional_parameter' if needed later, extracting name/type similarly
        # else: print(f"Debug: Unhandled node type in formal_parameter: {node.type}")

        # Extract name text
        if name_node:
            # If pattern is identifier (common case)
            if name_node.type == 'identifier' or name_node.type == 'this':
                 param_name = self.read_node_text(name_node)
            # Skip destructuring patterns as per requirements
            elif name_node.type in ('object_pattern', 'array_pattern'):
                 # print(f"Skipping destructuring parameter: {self.read_node_text(name_node)}")
                 return None # Skip complex parameters
            else: # Fallback if pattern is something else but contains text
                  param_name = self.read_node_text(name_node)


        # Extract type using helper
        # Ensure type_node is sought correctly even if name_node wasn't 'required_parameter'
        if type_node is None and node.type != 'identifier': # Check direct field if not found yet
            type_node = node.child_by_field_name("type")
        data_type = self.parse_type_annotation(type_node)

        # Return GIR dictionary for the parameter if name was found
        if param_name:
            return {
                "parameter_decl":{
                    "name": param_name,
                    "data_type": data_type,
                }
                
            }

        # print(f"Warning: Could not parse formal parameter node: {node.type} {self.read_node_text(node)}")
        return None # Parameter couldn't be parsed

    def class_declaration(self, node: Node, statements: list):
        #week3任务，解析class,class_body部分可用class_body函数帮助解析
        name_node = node.child_by_field_name("name")
        body_node = node.child_by_field_name("body")
        # heritage_node for extends/implements - skip as per requirements

        class_name = self.read_node_text(name_node) if name_node else f"<anonymous_class_{node.start_byte}>"

        # Parse modifiers like export, declare (using helper that checks context)
        attrs = self.parse_modifiers(node)

        body_gir = [] # List to hold GIR for class members
        if body_node and body_node.type == "class_body":
            # Call class_body helper, passing the list to populate
            self.class_body(body_node, body_gir)
        # else: class might be empty or syntax error

        # Assemble class GIR
        class_ir = {
            "class_declaration": {
                "name": class_name,
                "attrs": attrs, # Modifiers like export, default
                "fields": body_gir, # Populated by class_body call
                # Skip heritage/generics etc.
            }
        }
        statements.append(class_ir)
        return class_name

    def class_body(self, node, gir_node):
        #week3任务，解析class_body部分，需要解析类的字段与成员函数
        for member in node.named_children: # Iterate through direct members
            if self.is_comment(member):
                continue

            # Check member type and call appropriate handler
            # The handler will append its result to the body_gir list directly
            if member.type == "method_definition":
                # Use method_declaration to parse methods within class
                self.method_declaration(member, gir_node)
            elif member.type == "public_field_definition" or member.type == "field_definition":
                # Use public_field_definition for fields
                self.public_field_definition(member, gir_node)
            # Skip other member types as per requirements (static, abstract, decorators, index_signature, etc.)
            # elif member.type == "class_static_block": pass
            # elif member.type == "decorator": pass
            else:
                # Log or ignore unexpected members within a class body
                # print(f"Warning: Skipping unhandled class member type: {member.type}")
                pass
                   
    def public_field_definition(self, node: Node, statements: list):
        #week3任务, 解析类的字段
        # week3任务: 解析类的字段 (e.g., public name: string = "val";)
        # Handles public/private via parse_modifiers
        name_node = node.child_by_field_name("name")
        type_node = node.child_by_field_name("type")
        value_node = node.child_by_field_name("value") # Initializer

        # Handle both property_identifier and private_property_identifier (#name)
        field_name = self.read_node_text(name_node) if name_node else f"<unknown_field_{node.start_byte}>"

        # Parse modifiers (public, private, readonly)
        attrs = self.parse_modifiers(node)

        # Parse type annotation
        data_type = self.parse_type_annotation(type_node)

        # Parse initial value expression if present
        # Note: The statements list here is the class body's GIR list. Parsing the value
        # might add temporary variable assignments *before* the field definition if the
        # value expression is complex (e.g., involves function calls).
        # The 'value' stored in the field GIR should be the final result/variable.
        value = self.parse(value_node, statements) if value_node else None

        # Assemble field GIR
        field_ir = {
            "variable_decl": {
                "name": field_name,
                "attrs": attrs, # Includes public/private/readonly
                "data_type": data_type,
                "value": value, # Result of parsing the initial value expression
            }
        }
        # Append the field definition GIR *after* any statements generated by parsing its value
        statements.append(field_ir)
        return field_name

    # field_read表达式，解析如this.name操作，返回临时变量
    def member_expression(self, node: Node, statements: list,flag = 0):
        obj = self.parse(self.find_child_by_field(node, "object"), statements)
        property_ = self.parse(self.find_child_by_field(node, "property"), statements)
        tmp_var = self.tmp_variable(node)
        statements.append({"field_read": {"target": tmp_var, "receiver_object": obj, "field": property_}})
        return tmp_var

    # 二元表达式，解析如a + b操作，返回临时变量
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
    # return语句，解析如return a操作，返回临时变量
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


