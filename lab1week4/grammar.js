module.exports = grammar({
  name: 'typescript',
  extras: $ => [
    $.comment,
    /\s/,  // Whitespace
    /[\s\p{Zs}\uFEFF\u2028\u2029\u2060\u200B]/,
  ],
  // 指定优先级
  precedences: $ => [
    [
      $.update_expression,
      'binary_times',
      'binary_plus',
      'binary_relation',
      'binary_equality',
    ],
  ],
  // 处理冲突
  conflicts: $ => [
    [$.update_expression, $.expression_statement],
    [$.update_expression, $.variable_declaration]
  ],

  word: $ => $.identifier,
  rules: {
    program: $ => seq(
      optional($.hash_bang_line),
      repeat($.statement),
    ),

    hash_bang_line: _ => /#!.*/,

    statement: $ => choice(
      $.declaration,
      $.statement_block,
      $.expression_statement,
      $.statement_block,
      $.if_statement,
      $.for_statement,
    ),

    for_statement: $ => seq(
      // week4 for语句
      'for',
      '(',
      field('init', optional(choice(
        seq(
          $.expression,
          repeat(seq(',', $.expression))
        ),
        $.for_var_declaration),
      )),
      ';',
      field('condition', optional($.expression)),
      ';',
      field('update', optional(
        seq(
          $.expression,
          repeat(seq(',', $.expression)))
        )
      ),
      ')',
      field('body', $.statement)
    ),

    binary_expression: $ => choice(
      ...[
        ['+', 'binary_plus'],
        ['-', 'binary_plus'],
        ['*', 'binary_times'],
        ['/', 'binary_times'],
        ['%', 'binary_times'],
        ['<', 'binary_relation'],
        ['<=', 'binary_relation'],
        ['==', 'binary_equality'],
        ['===', 'binary_equality'],
        ['!=', 'binary_equality'],
        ['!==', 'binary_equality'],
        ['>=', 'binary_relation'],
        ['>', 'binary_relation'],
      ].map(([operator, precedence, associativity]) =>
        (associativity === 'right' ? prec.right : prec.left)(precedence, seq(
          // week4 识别二元操作binary_expression
          field('left', $.expression),
          field('operator', operator),
          field('right', $.expression)
        )),
      ),
    ),

    update_expression: $ => prec.left(choice(
      seq(
        field('argument', $.expression),
        field('operator', choice('++', '--')),
      ),
      seq(
        field('operator', choice('++', '--')),
        field('argument', $.expression),
      ),
    )),

    if_statement: $ => prec.right(seq(
      //week3 if语句
      "if",
      field("condition", $.parenthesized_expression),
      field("consequence", $.statement),
      optional(seq(
          "else", 
          field("alternative", $.statement)
      ))
  )),
  
  parenthesized_expression: $ => seq(
      //week3 括号表达式,用于if_statement的条件部分
      "(",
      $.expression,
      ")"
  ),


  variable_declaration: $ => choice(
      // const声明必须初始化
      seq(
        field('kind', 'const'),
        field('name', $.identifier), // 变量名
        optional(field('type', $.type_annotation)), // 可选的类型注解
        seq('=', field('value', $.expression)), // 初始化表达式是必须的
        repeat(seq(
          ',', 
          field('name', $.identifier), // 变量名
          optional(field('type', $.type_annotation)), // 可选的类型注解
          seq('=', field('value', $.expression)),
          )// 初始化表达式是必须的))
        ),
        optional($._semicolon),
    ),
    // let声明初始化表达式是可选的
    seq(
        field('kind', 'let'),
        field('name', $.identifier),
        optional(field('type', $.type_annotation)),
        optional(seq('=', field('value', $.expression))), // 初始化表达式是可选的
        repeat(seq(
          ',', 
          field('name', $.identifier), // 变量名
          optional(field('type', $.type_annotation)), // 可选的类型注解
          optional(seq('=', field('value', $.expression))),
          )// 初始化表达式是必须的))
        ),
        optional($._semicolon),
    )
  ),

  for_var_declaration: $ => choice(
      // const声明必须初始化
      seq(
          field('kind', 'const'),
          field('name', $.identifier), // 变量名
          optional(field('type', $.type_annotation)), // 可选的类型注解
          seq('=', field('value', $.expression)), // 初始化表达式是必须的
          repeat(seq(
            ',', 
            field('name', $.identifier), // 变量名
            optional(field('type', $.type_annotation)), // 可选的类型注解
            seq('=', field('value', $.expression)),
            )// 初始化表达式是必须的))
          )
      ),
      // let声明初始化表达式是可选的
      seq(
          field('kind', 'let'),
          field('name', $.identifier),
          optional(field('type', $.type_annotation)),
          optional(seq('=', field('value', $.expression))), // 初始化表达式是可选的
          repeat(seq(
            ',', 
            field('name', $.identifier), // 变量名
            optional(field('type', $.type_annotation)), // 可选的类型注解
            optional(seq('=', field('value', $.expression))),
          )// 初始化表达式是必须的))
        )
      )
  ),


    number: _ => {
          //week2任务，16进制数的正则表达式
          const hex_literal = /0[xX][0-9a-fA-F]+/;

          //week2任务，10进制数的正则表达式
          const decimal_digits = /[0-9]+/;

      return token(choice(
        hex_literal,
        decimal_digits,
      ));
    },
    expression_statement: $ => seq(
      $.expression,
      optional($._semicolon),
    ),
    expression: $ => choice(
      $.assignment_expression,
      $.identifier,
      $.number,
      $.binary_expression,
      $.update_expression,
    ),

    assignment_expression: $ => prec.right(seq(
      optional('using'),
      field('left', $.identifier),
      '=',
      field('right', $.expression),
    )),

    declaration: $ => choice(
      $.function_declaration,
      $.variable_declaration,
    ),

    function_declaration: $ => prec.right(seq(
      optional('async'),
      'function',
      field('name', $.identifier),
      $.call_signature,
      field('body', $.statement_block),
      optional($._semicolon),
    )),

    formal_parameters: $ => seq(
      '(',
      //week2任务，支持简单参数，包括类型注解。匹配的内容为 (b:number, c:any)
      //hint1: 匹配零个或多个由逗号分隔的元素，可以使用辅助函数commaSep
      //hint2："$."用于引用当前grammar.js中定义的其他语法规则，如$.type_annotation->引用名为type_annotation的规则
      // commaSep(seq($.identifier, optional($.type_annotation))),
      commaSep(seq(
          field('name', $.identifier),
          field('type', optional($.type_annotation))
      )),
      ')',
  ),

  call_signature: $ => seq(
      //week2任务，函数的调用签名，包括参数与返回类型 。匹配的内容为 (b:number, c:any):void
      $.formal_parameters, // 引用 formal_parameters 规则
      $.type_annotation  // 返回类型注释
  ),
    required_parameter: $ => seq(
      $.identifier,
      field('type', optional($.type_annotation)),
    ),


    type_annotation: $ => seq(
      ':', $.primitive_type,
    ),

    primitive_type: _ => choice(
      'any', 'number', 'boolean', 'string', 'symbol', 'void', 'unknown', 'string', 'never', 'object',
    ),
    statement_block: $ => prec.right(seq(
      '{',
      repeat($.statement),
      '}',
      optional($._semicolon),
    )),


    comment: $ => choice(
      token(choice(
        seq('//', /.*/),
        seq(
          '/*',
          /[^*]*\*+([^/*][^*]*\*+)*/,
          '/',
        ),
      )),
    ),



    identifier: $ => /[_a-zA-Z][_a-zA-Z0-9]*/,

    // 分号
    _semicolon: $ => ';',

  }

})



function commaSep1(rule) {
  return seq(rule, repeat(seq(',', rule)));
}

function commaSep(rule) {
  return optional(commaSep1(rule));
}

function sepBy1(sep, rule) {
  return seq(rule, repeat(seq(sep, rule)));
}
