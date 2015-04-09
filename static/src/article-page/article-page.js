angular.module('articlePage', [
    'ngRoute',
    'articleService'
  ])



  .config(function($routeProvider) {
    $routeProvider.when('/article/:pmid', {
      templateUrl: 'article-page/article-page.tpl.html',
      controller: 'articlePageCtrl'
    })
  })



  .controller("articlePageCtrl", function($scope,
                                          $http,
                                          $routeParams,
                                          ArticleService){

    console.log("article page!", $routeParams)

    ArticleService.getArticle($routeParams.pmid)

    $scope.ArticleService = ArticleService


    $scope.dotPosition = function(scalingFactor, seed){

      var verticalJitter = randomPlusOrMinus(15, seed)
      var horizontalJitterPercent = randomPlusOrMinus(0.5,seed.substring(0, 7))
      var scalingFactorPercent = (scalingFactor * 100) + horizontalJitterPercent

      var ret = "left: " + scalingFactorPercent + "%;"
      ret += "top:" + verticalJitter + "px;"
      return ret
    }


    // not using this right now
    function rand(seed) {
        var x = Math.sin(seed) * 10000;
        return x - Math.floor(x);
    }

    function randomPlusOrMinus(range, seed){

      console.log("random number is: ", seed)
      Math.seedrandom(seed)

      var pick = range * Math.random()
      pick *= (Math.random() > .5 ? -1 : 1)

      return pick
    }


  })  


