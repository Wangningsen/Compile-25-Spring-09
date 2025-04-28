# <center>Lab2 Week3</center>
<center>王宁森 周子轩</center>
<center>22307130058 22307130401</center>

## 截图


## 解析class

## 完善assign_stmt

完善assign_stmt,使其支持左侧为object.property的情况，对应GIR指令为field_write

```python
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
                    "operand": value,
                }
            }
            statements.append(stmt)
            return value

        else:
            self.parse(left_node, statements)
            return value  
```

现在的`assignment_expression`方法在继承了上周处理简单变量（标识符）到简单值（标识符或字面量）赋值并生成 `assign_stmt` 指令的基础上，扩展了左值的支持范围,能够识别并处理`object.property`形式的赋值。通过判断左侧 `AST` 节点的类型 (`member_expression` 或 `subscript_expression`)，该方法会调用专门的辅助函数 `self.parse_field` 来解析出要操作的对象（`receiver_object`）和要访问的属性（`field`），并结合右侧表达式解析得到的 `value`，生成更具体的 `field_write` 中间表示指令，从而实现对对象属性或集合元素的赋值的 `GIR` 转换。

## 完善method_definition

完善method_definition, 使其支持简单参数与类型，不要求支持可选参数、默认参数等复杂参数情况，
不要求支持复杂类型（联合类型、泛型等）