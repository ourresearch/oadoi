angular.module('profilePage', [
    'ngRoute',
    'profileService'
  ])



  .config(function($routeProvider) {
    $routeProvider.when('/u/:slug', {
      templateUrl: 'profile-page/profile.tpl.html',
      controller: 'profilePageCtrl',
      resolve: {
        product: function(ProfileService, $route){
          return ProfileService.getProfile($route.current.params.slug)
        }
      }
    })
  })



  .controller("profilePageCtrl", function($scope,
                                          $routeParams,
                                          ProfileService){

    console.log("foo", ProfileService.data)

    console.log("$routeParams", $routeParams)

    $scope.ProfileService = ProfileService

  })


